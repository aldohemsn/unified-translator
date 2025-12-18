"""
Legal Translation Strategy
Implements CIL (Context-Insight-Logic) methodology for legal translation.
"""
import csv
import logging
import os
import json
from typing import List, Dict, Any, Optional
from .base_strategy import BaseStrategy
from core.llm_client import LLMClient
from core.context_window import ContextWindowBuilder
from core.tsv_handler import TSVHandler

logger = logging.getLogger(__name__)


class LegalStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "LegalStrategy"
        self._strategy_config = self._get_strategy_config('legal')
        self.glossary: Dict[str, str] = {}
        self.glossary_path = None
        
        # Style Guide
        self.style_guide_path = None
        self.style_guide_content = ""
        
        # CIL Knowledge Context
        self.context_note = ""      # Context: Topic, Tone, Audience
        self.domain_insights = ""   # Insight: Domain Analysis + Key Terms + Pitfalls
        self.layman_logic = ""      # Logic: Feynman-style explanation
        
        # Semantic Segments (for optimized batching)
        self.semantic_segments: List[Dict[str, int]] = []  # [{"start": 0, "end": 5}, ...]

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Load glossary, style guide, generate CIL context, and perform semantic segmentation.
        """
        # 1. Load Glossary
        if context_files and 'glossary' in context_files:
            self.glossary_path = context_files['glossary']
            self._load_glossary(self.glossary_path)
            
        # 2. Load Style Guide
        if context_files and 'style_guide' in context_files:
            self.style_guide_path = context_files['style_guide']
            self._load_style_guide(self.style_guide_path)
            
        # 3. Generate CIL Context (if source file provided or use input)
        source_path = context_files.get('source', input_file_path) if context_files else input_file_path
        self._generate_cil_context(source_path)
        
        # 4. Perform Semantic Segmentation
        self._generate_semantic_segments(source_path)

    def _load_style_guide(self, path: str):
        """Load Style Guide content."""
        if not os.path.exists(path):
            logger.warning(f"Style guide file not found: {path}")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.style_guide_content = f.read().strip()
            logger.info(f"Loaded style guide from {path} ({len(self.style_guide_content)} chars).")
        except Exception as e:
            logger.error(f"Error loading style guide: {e}")
            
    def _generate_semantic_segments(self, file_path: str) -> None:
        """
        Use LLM to divide document into semantic segments (complete legal arguments).
        Analyzes the full text in batches of 200 lines.
        Auto-merges small segments to ensure efficiency.
        """
        logger.info("Generating semantic segments for full text...")
        
        try:
            handler = TSVHandler()
            rows = handler.read_file(file_path)
            if not rows or len(rows) < 2:
                self.semantic_segments = []
                return
            
            raw_segments = []
            analysis_batch_size = 200
            total_rows = len(rows)
            
            segmentation_model = self.get_model_for_stage('segmentation')
            llm = LLMClient(self.config)

            for batch_start in range(0, total_rows, analysis_batch_size):
                batch_end = min(batch_start + analysis_batch_size, total_rows)
                chunk_rows = rows[batch_start:batch_end]
                
                logger.info(f"Analyzing segmentation for lines {batch_start}-{batch_end}...")

                lines_text_parts = []
                for i, row in enumerate(chunk_rows):
                    source = row.get('Source', '')[:100].replace('\n', ' ')
                    lines_text_parts.append(f"{i}: {source}")
                
                lines_text = "\n".join(lines_text_parts)
                
                # Dynamic max lines in prompt based on chunk size
                relative_max = len(chunk_rows) - 1

                segment_prompt = f"""分析以下法律文本（第 {batch_start} - {batch_end} 行），按【完整语意群】划分。

目标：将文本划分为较大的语义块，以便进行上下文连贯的翻译。
每个语义块应当包含至少 4 行，除非是独立的标题或极短的条款。

输入格式：
相对行号: 内容摘要

{lines_text}

输出格式 (JSON数组):
[{{"start": 0, "end": 5}}, {{"start": 6, "end": 15}}, ...]

注意：
- start 和 end 是基于提供文本的相对行号（0-{relative_max}）
- 必须覆盖所有行，从 0 到 {relative_max}，不遗漏任何一行
- 优先合并短句，避免碎片化
"""
                
                try:
                    response = llm.generate(segment_prompt, model=segmentation_model, response_mime_type="application/json")
                    segments = json.loads(response)
                    
                    # Validate coverage for this batch
                    # We need to ensure continuity within the batch
                    
                    current_batch_segments = []
                    last_end = -1
                    
                    for seg in segments:
                        if isinstance(seg, dict) and 'start' in seg and 'end' in seg:
                            rel_start = int(seg['start'])
                            rel_end = int(seg['end'])
                            
                            # Sanity checks
                            rel_start = max(0, rel_start)
                            rel_end = min(rel_end, relative_max)
                            
                            if rel_start > rel_end: 
                                continue
                                
                            # Check for gaps
                            if rel_start > last_end + 1:
                                # Fill gap
                                gap_start = last_end + 1
                                gap_end = rel_start - 1
                                current_batch_segments.append({
                                    "start": gap_start + batch_start,
                                    "end": gap_end + batch_start
                                })
                            
                            abs_start = rel_start + batch_start
                            abs_end = rel_end + batch_start
                            current_batch_segments.append({
                                "start": abs_start,
                                "end": abs_end
                            })
                            last_end = rel_end

                    # Check for trailing gap in batch
                    if last_end < relative_max:
                        current_batch_segments.append({
                            "start": (last_end + 1) + batch_start,
                            "end": relative_max + batch_start
                        })
                    
                    raw_segments.extend(current_batch_segments)
                            
                except Exception as e:
                    logger.warning(f"Segmentation failed for batch {batch_start}-{batch_end}: {e}")
                    # Fallback: create a single segment for this entire batch
                    raw_segments.append({"start": batch_start, "end": batch_end - 1})

            # --- Post-Processing: Merge Small Segments ---
            merged_segments = []
            
            # Configuration for merging
            TARGET_CHARS = 1500      # Aim for ~1500 chars per batch (approx 500-800 tokens)
            MAX_LINES_PER_BATCH = 40 # Hard limit to prevent JSON complexity issues
            
            if not raw_segments:
                self.semantic_segments = []
                return

            def get_segment_text_len(seg_start, seg_end):
                """Calculate total character length of a segment range."""
                length = 0
                for i in range(seg_start, seg_end + 1):
                    if i < len(rows):
                        length += len(rows[i].get('Source', ''))
                return length

            current_seg = raw_segments[0]
            current_char_count = get_segment_text_len(current_seg['start'], current_seg['end'])
            
            for next_seg in raw_segments[1:]:
                next_char_count = get_segment_text_len(next_seg['start'], next_seg['end'])
                
                current_lines = current_seg['end'] - current_seg['start'] + 1
                next_lines = next_seg['end'] - next_seg['start'] + 1
                total_lines = current_lines + next_lines
                total_chars = current_char_count + next_char_count
                
                # Merge criteria:
                # 1. Combined lines must be within MAX_LINES_PER_BATCH
                # 2. Merge if current batch is "underfilled" (less than TARGET_CHARS)
                #    OR if the next segment is tiny (e.g. < 50 chars) and fits easily
                
                should_merge = False
                
                if total_lines <= MAX_LINES_PER_BATCH:
                    if current_char_count < TARGET_CHARS:
                        should_merge = True
                    elif next_char_count < 100: # Always gobble up tiny stragglers if space permits
                        should_merge = True
                
                if should_merge:
                    # Merge next into current
                    current_seg['end'] = next_seg['end']
                    current_char_count = total_chars
                else:
                    # Finalize current and move to next
                    merged_segments.append(current_seg)
                    current_seg = next_seg
                    current_char_count = next_char_count
            
            # Append the last segment
            merged_segments.append(current_seg)
            
            self.semantic_segments = merged_segments
            logger.info(f"✓ Generated {len(self.semantic_segments)} semantic segments (after merging small chunks).")
            
        except Exception as e:
            logger.warning(f"Semantic segmentation process failed: {e}. Using default batching.")
            self.semantic_segments = []
    
    def get_batch_boundaries(self, total_rows: int) -> List[tuple]:
        """
        Return batch boundaries based on semantic segments.
        Falls back to row-by-row if no segments available.
        """
        if self.semantic_segments:
            return [(seg['start'], seg['end'] + 1) for seg in self.semantic_segments]
        else:
            # Fallback: row-by-row (original behavior)
            return [(i, i + 1) for i in range(total_rows)]

    def _load_glossary(self, path: str):
        """Load TSV glossary file."""
        if not os.path.exists(path):
            logger.warning(f"Glossary file not found: {path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter='\t')
                header = next(reader, None)
                
                # Simple header detection
                if header and header[0].lower() in ['english', 'term', 'source', 'en', 'en_term']:
                    pass  # Header skipped
                else:
                    # Treat as data if not clearly a header
                    if header and len(header) >= 2:
                        self.glossary[header[0].strip()] = header[1].strip()
                
                for row in reader:
                    if len(row) >= 2:
                        self.glossary[row[0].strip()] = row[1].strip()
            
            logger.info(f"Loaded {len(self.glossary)} terms from glossary.")
        except Exception as e:
            logger.error(f"Error loading glossary: {e}")

    def _generate_cil_context(self, file_path: str):
        """
        Generate CIL (Context-Insight-Logic) knowledge using LLM.
        """
        logger.info("Generating CIL knowledge context...")
        
        try:
            handler = TSVHandler()
            rows = handler.read_file(file_path)
            if not rows:
                return
            
            # Simple assumption: Source texts are in 'Source' column
            source_texts = [r.get('Source', '') for r in rows[:100]] 
            full_text = ' '.join(source_texts)[:5000]
        except Exception as e:
            logger.warning(f"Could not read file for CIL: {e}")
            return
        
        if not full_text:
            return
        
        preprocessing_model = self.get_model_for_stage('preprocessing')
        
        try:
            llm = LLMClient(self.config)
            
            # 1. CONTEXT
            context_prompt = f"""Analyze the following legal text.
Identify: Core topic, Document type, Intended audience, General tone.
Summarize in one concise paragraph (under 100 words).

Text:
"{full_text[:3000]}"
"""
            self.context_note = llm.generate(context_prompt, model=preprocessing_model).strip()
            logger.info("✓ Context generated")
            
            # 2. INSIGHT
            insight_prompt = f"""ROLE: Senior Legal Analyst.
TASK: Passage Insight.
GLOBAL CONTEXT: "{self.context_note}"

1. Identify specific micro-domain (e.g. "HK IP Litigation").
2. Define 3-5 Key Terms.
3. Flag "False Friends" or pitfalls.

OUTPUT:
- Domain Context: ...
- Key Definitions: ...
- Pitfalls: ...

TEXT:
"{full_text[:3000]}"
"""
            self.domain_insights = llm.generate(insight_prompt, model=preprocessing_model).strip()
            logger.info("✓ Insight generated")
            
            # 3. LOGIC (Conditional based on config)
            if self.should_enable_layman_logic():
                logic_prompt = f"""ROLE: "Layman in the Loop" (Feynman Technique).
CONTEXT: {self.context_note[:500]}

1. Explain what this text *means* to an outsider.
2. Extract the LOGIC. No word-for-word translation.
3. Explain in the OPPOSITE language of the source.

TEXT:
"{full_text[:3000]}"
"""
                self.layman_logic = llm.generate(logic_prompt, model=preprocessing_model, temperature=0.7).strip()
                logger.info("✓ Layman's Logic generated")
            else:
                logger.info("⏭ Layman's Logic skipped (disabled in config)")
            
        except Exception as e:
            logger.error(f"CIL generation failed: {e}")
            self.context_note = "Legal Translation Context (General)"

    def _build_cil_prompt(self) -> str:
        """Build the full CIL prompt section."""
        glossary_lines = [f"- {k} -> {v}" for k, v in self.glossary.items()]
        glossary_text = "\n".join(glossary_lines) if glossary_lines else "(No glossary provided)"
        
        style_section = ""
        if self.style_guide_content:
            style_section = f"""
【2.8 STYLE & TONE GUIDELINES (STRICT)】
{self.style_guide_content}
"""
        
        return f"""=== CIL TRANSLATION METHODOLOGY ===

【1. CONTEXT - Document Background】
{self.context_note or "(Not available)"}

【2. INSIGHT - Domain Analysis】
{self.domain_insights or "(See glossary below)"}

【2.5 MANDATORY GLOSSARY】
The following terminology MUST be used EXACTLY as specified.
DO NOT use any alternative translations. This is NON-NEGOTIABLE.

{glossary_text}
{style_section}
【3. LAYMAN'S LOGIC - Feynman Explanation】
{self.layman_logic or "(Not available)"}

=== END CIL ==="""

    def _enforce_glossary(self, source: str, target: str) -> str:
        """
        Post-LLM compliance check.
        """
        violations = []
        for term_en, term_cn in self.glossary.items():
            if term_en in source:
                options = [opt.strip() for opt in term_cn.split('/')]
                # Simple check: if NONE of the options appear in target
                # Note: This can be flaky with subsets of words, but serves as a basic check
                if not any(opt in target for opt in options):
                    # Double check if English term itself is in target (sometimes kept as is)
                    if term_en not in target:
                        violations.append(f"{term_en} should be {term_cn}")
        
        if violations:
            target += f" <<<GLOSSARY_VIOLATION: {'; '.join(violations)}>>>"
        
        return target

    def get_external_review_prompt(self) -> str:
        """
        Generates a comprehensive system instruction for an external LLM 
        to review the final exported DOCX against the source DOCX.
        """
        glossary_lines = [f"- {k} :: {v}" for k, v in self.glossary.items()]
        glossary_text = "\n".join(glossary_lines) if glossary_lines else "(No specific glossary provided)"
        
        return f"""You are a Senior Legal Translation QA Specialist.

【Task】
Your task is to review the attached translated document (Simplified Chinese) against the provided original source document (English).
You must ensure the translation is accurate, legally precise, and strictly adheres to the project's terminology standards.

【Document Context】
{self.context_note or "General Legal Document"}

【Domain Insights & Critical Constraints】
{self.domain_insights or "Standard legal terminology applies."}

【Mandatory Glossary】
A specific glossary file (TSV format) has been provided with this request.
You must strictly cross-reference this glossary file against the translation.
Any deviation from the terms defined in the attached glossary is a CRITICAL ERROR.

(Quick Reference - Key Terms):
{glossary_text}

【Review Guidelines】
1. **Accuracy**: Verify that all legal obligations, rights, and definitions are translated accurately without ambiguity.
2. **Consistency**: Ensure the Mandatory Glossary is used consistently throughout the document.
3. **Style**: The target text must be in professional, formal Simplified Chinese (avoiding "translationese").
4. **Formatting**: Check that the structure (clause numbering, bolding) matches the source.

【Output Format】
Please provide a report in the following format:
- **Critical Issues**: (Glossary violations, missing content, major mistranslations)
- **Suggestions**: (Stylistic improvements)
- **Overall Assessment**: (Pass / Needs Revision)
"""

    def process_batch(
        self, 
        llm_client: LLMClient, 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: ContextWindowBuilder
    ) -> List[Dict[str, str]]:
        """
        Process the ENTIRE semantic segment in a SINGLE LLM call.
        Supports CROSS-ROW MERGING of translation.
        Handles LOCKED rows (context only, no translation).
        """
        cil_prompt = self._build_cil_prompt()
        
        lines_input = []
        ids_map = {} 
        
        for i, row in enumerate(batch_rows):
            rid = row.get('ID', str(i))
            ids_map[i] = rid
            source = row.get('Source', '')
            target = row.get('Target', '')
            is_locked = row.get('LOCKED', '0') == '1'
            
            if is_locked:
                 lines_input.append(f"[{i}] [LOCKED] {source}")
            elif target:
                lines_input.append(f"[{i}] REVIEW_TARGET: {target} (SOURCE: {source})")
            else:
                lines_input.append(f"[{i}] SOURCE: {source}")
        
        content_block = "\n".join(lines_input)
        
        system_prompt = f"""You are a legal translation expert.

{cil_prompt}

【Task】
Translate the provided block of text into **Simplified Chinese (简体中文)**.
The input is a SEMANTICALLY COHERENT SEGMENT.

【Merge Rules】
1. You MAY merge multiple source lines into a single target line if they form a single sentence/logic unit.
2. If you merge Content from Line X into Line Y:
   - Line Y should contain the full translation.
   - Line X MUST return exactly: "[[MERGED_UP]]" (if merged into previous) or "[[MERGED_DOWN]]" (if merged into next).
   - Use "[[MERGED_UP]]" preferably when merging with preceding lines.
   
3. STRICT ROW ALIGNMENT:
   - You MUST provide a JSON output key for EVERY input index (0 to {len(batch_rows)-1}).
   - No index should be missing.
   - For lines marked [LOCKED], return "<<<LOCKED>>>" as the value.

【Glossary & Logic】
- Adhere strictly to the Glossary.
- Ensure context coherence.
- **Target Language**: Simplified Chinese.
- **Handling English**: Translate English text into Chinese. Only retain English for proper nouns, codes, formulas, or specific legal citations where keeping the original is standard practice.

【Output Format】
Return a JSON object mapping index to translation.
Example:
{{
  "0": "第0行和第1行的完整翻译",
  "1": "[[MERGED_UP]]",
  "2": "[[LOCKED]]"
}}
"""
        
        prompt = f"""
【Input Segment】
{content_block}

【Output (JSON)】
"""
        processed_batch = []
        
        try:
            translation_model = self.get_model_for_stage('translation')
            response = llm_client.generate(prompt, system_instruction=system_prompt, model=translation_model, response_mime_type="application/json")
            
            try:
                results_map = json.loads(response)
            except json.JSONDecodeError:
                # Fallback: try to find JSON block if mixed with text
                import re
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    results_map = json.loads(match.group(0))
                else:
                    raise ValueError("Could not parse JSON response")

            # Map results back to rows
            for i, row in enumerate(batch_rows):
                idx_str = str(i)
                is_locked = row.get('LOCKED', '0') == '1'

                if is_locked:
                    # For locked rows, keep original Target content.
                    # If original Target is empty, it should remain empty.
                    final_translation = row.get('Target')
                    processed_batch.append({
                        'ID': row['ID'],
                        'Source': row['Source'],
                        'Target': final_translation,
                        'LOCKED': '1'
                    })
                elif idx_str in results_map:
                    raw_translation = results_map[idx_str]
                    
                    if raw_translation == "[[LOCKED]]":
                        # Should have been handled by is_locked check, but just in case
                         final_translation = row.get('Source')
                    elif "[[MERGED_UP]]" in raw_translation: # Still support old format coming from LLM
                        final_translation = "<<<已向上合并>>>"
                    elif "[[MERGED_DOWN]]" in raw_translation: # Still support old format coming from LLM
                        final_translation = "<<<已向下合并>>>"
                    else:
                        clean_translation = raw_translation.replace("，，", "，")
                        final_translation = self._enforce_glossary(row.get('Source', ''), clean_translation)
                    
                    processed_batch.append({
                        'ID': row['ID'],
                        'Source': row['Source'],
                        'Target': final_translation,
                        'LOCKED': row.get('LOCKED', '0')
                    })
                else:
                    logger.warning(f"Missing translation for index {i} in batch response. Using placeholder.")
                    processed_batch.append({
                        'ID': row['ID'],
                        'Source': row['Source'],
                        'Target': "<<<MISSING_TRANSLATION>>>", # Better to flag than ignore
                        'LOCKED': row.get('LOCKED', '0')
                    })
                    
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Fallback: return original rows
            processed_batch.extend(batch_rows)
            
        return processed_batch
