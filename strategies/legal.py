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
from ..core.llm_client import LLMClient
from ..core.context_window import ContextWindowBuilder

logger = logging.getLogger(__name__)


class LegalStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "LegalStrategy"
        self.glossary: Dict[str, str] = {}
        
        # CIL Knowledge Context
        self.context_note = ""      # Context: Topic, Tone, Audience
        self.domain_insights = ""   # Insight: Domain Analysis + Key Terms + Pitfalls
        self.layman_logic = ""      # Logic: Feynman-style explanation

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Load glossary and generate CIL context using LLM.
        """
        # 1. Load Glossary
        if context_files and 'glossary' in context_files:
            glossary_path = context_files['glossary']
            self._load_glossary(glossary_path)
            
        # 2. Generate CIL Context (if source file provided or use input)
        source_path = context_files.get('source', input_file_path) if context_files else input_file_path
        self._generate_cil_context(source_path)

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
                if header and header[0].lower() in ['english', 'term', 'source', 'en']:
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
            from ..core.tsv_handler import TSVHandler
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
        
        knowledge_model = self.config.get('strategies', {}).get('legal', {}).get(
            'cil_model', 
            self.config.get('llm', {}).get('knowledge_model', 'gemini-2.5-pro')
        )
        
        try:
            llm = LLMClient(self.config)
            
            # 1. CONTEXT
            context_prompt = f"""Analyze the following legal text.
Identify: Core topic, Document type, Intended audience, General tone.
Summarize in one concise paragraph (under 100 words).

Text:
"{full_text[:3000]}"
"""
            self.context_note = llm.generate(context_prompt, model=knowledge_model).strip()
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
            self.domain_insights = llm.generate(insight_prompt, model=knowledge_model).strip()
            logger.info("✓ Insight generated")
            
            # 3. LOGIC
            logic_prompt = f"""ROLE: "Layman in the Loop" (Feynman Technique).
CONTEXT: {self.context_note[:500]}

1. Explain what this text *means* to an outsider.
2. Extract the LOGIC. No word-for-word translation.
3. Explain in the OPPOSITE language of the source.

TEXT:
"{full_text[:3000]}"
"""
            self.layman_logic = llm.generate(logic_prompt, model=knowledge_model, temperature=0.7).strip()
            logger.info("✓ Layman's Logic generated")
            
        except Exception as e:
            logger.error(f"CIL generation failed: {e}")
            self.context_note = "Legal Translation Context (General)"

    def _build_cil_prompt(self) -> str:
        """Build the full CIL prompt section."""
        glossary_lines = [f"- {k} -> {v}" for k, v in self.glossary.items()]
        glossary_text = "\n".join(glossary_lines) if glossary_lines else "(No glossary provided)"
        
        return f"""=== CIL TRANSLATION METHODOLOGY ===

【1. CONTEXT - Document Background】
{self.context_note or "(Not available)"}

【2. INSIGHT - Domain Analysis】
{self.domain_insights or "(See glossary below)"}

【2.5 MANDATORY GLOSSARY】
The following terminology MUST be used EXACTLY as specified.
DO NOT use any alternative translations. This is NON-NEGOTIABLE.

{glossary_text}

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
                if not any(opt in target for opt in options):
                    violations.append(f"{term_en} should be {term_cn}")
        
        if violations:
            target += f" [[GLOSSARY_VIOLATION: {'; '.join(violations)}]]"
        
        return target

    def process_batch(
        self, 
        llm_client: LLMClient, 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: ContextWindowBuilder
    ) -> List[Dict[str, str]]:
        """
        Process using sliding window PER ROW (legal precision mode).
        Use ContextWindowBuilder properly.
        """
        processed_batch = []
        cil_prompt = self._build_cil_prompt()
        
        system_prompt = f"""You are a legal translation expert specializing in Hong Kong law.

{cil_prompt}

【Task】
Review the Target translation for the marked segment.
1. Check Glossary compliance first.
2. Ensure logic flow (Logic).
3. Ensure context coherence (Context).
4. Fix grammar/punctuation.

【CRITICAL WARNING】
If you use a translation different from the Glossary, your output will be REJECTED.

【Output Format】
Return ONLY the corrected Target text. If no changes, return original.
"""
        
        # We need ALL history + current batch available for the window builder
        # 'history_rows' contains previously processed rows (all prior batches)
        # 'processed_batch' contains previously processed rows in THIS batch
        
        # But wait, 'window_builder' was initialized with ALL raw data in 'Processor.run'.
        # However, for the BEST context, we should ideally show the *corrected* versions of previous rows.
        # The 'window_builder' passed from Processor typically holds raw rows.
        # Let's see if we can use 'history_rows' to patch the window dynamically or 
        # build a local window if strict sequential dependency is needed.
        
        # For simplicity and standard compliance with Processor, we use the passed 'window_builder' 
        # to get the SURROUNDING context (which might look at raw future rows, and raw past rows).
        # IMPROVEMENT: If we want to show *corrected* past rows, we'd need to update the window builder's data 
        # or construct windows manually here. Given `window_builder.build(index)` works on indices relative to total data.
        
        # We need to know the GLOBAL index of the current row to query the window builder.
        # This is strictly tricky if we don't pass global indices.
        # Let's Assume batch_rows have 'ID' which *might* map to index if numeric, but safest is to rely on passed objects.
        
        # Workaround: Recalculate global index? 
        # Actually Processor calls process_batch. 
        # Let's rely on standard sliding window textual construction manually if needed, 
        # OR assume we just use the local batch context if global is hard.
        
        # BETTER APPROACH matching `legal-translation-cil`:
        # Reconstruct window locally using history + batch.
        
        full_context_data = history_rows + batch_rows # Use raw for current batch initially
        history_len = len(history_rows)
        
        for i, row in enumerate(batch_rows):
            source = row.get('Source', '')
            target = row.get('Target', '')
            
            if not source.strip():
                processed_batch.append(row)
                continue
            
            # Consturct window locally
            # Before: last 3 from (history + processed_so_far)
            # After: next 2 from (rest of batch)
            
            current_processed_so_far = processed_batch 
            available_past = history_rows + current_processed_so_far
            
            # Build window string manually for clarity and precision
            window_parts = []
            
            # Past 3
            start_past = max(0, len(available_past) - 3)
            for p_row in available_past[start_past:]:
                window_parts.append(f"[Segment {p_row.get('ID')}]: {p_row.get('Source')} -> {p_row.get('Target')}")
            
            # Current
            window_parts.append(f">>> [Segment {row.get('ID')} - TARGET]:\n    Source: {source}\n    Target: {target}")
            
            # Future 2 (from remaining batch_rows)
            for f_row in batch_rows[i+1 : i+3]:
                 window_parts.append(f"[Segment {f_row.get('ID')}]: {f_row.get('Source')}...")
            
            context_window_str = "\n".join(window_parts)
            
            prompt = f"""【Context Window】
{context_window_str}

Please review and correct the Target for the marked segment."""

            try:
                corrected = llm_client.generate(prompt, system_instruction=system_prompt).strip()
                corrected = corrected.replace("，，", "，")
                corrected = self._enforce_glossary(source, corrected)
                
                processed_batch.append({
                    'ID': row['ID'],
                    'Source': source,
                    'Target': corrected
                })
            except Exception as e:
                logger.warning(f"Row {row.get('ID')} error: {e}")
                processed_batch.append(row)
                
        return processed_batch
