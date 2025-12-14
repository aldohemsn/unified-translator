"""
Academic Translation Strategy
Implements Dual-Persona (Translator + Editor) workflow with Cross-Row Merging and QA Check.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from .base_strategy import BaseStrategy
from core.llm_client import LLMClient
from core.context_window import ContextWindowBuilder
from core.tsv_handler import TSVHandler

logger = logging.getLogger(__name__)

class AcademicStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "AcademicStrategy"
        self._strategy_config = self._get_strategy_config('academic')
        
        # Dual Personas
        self.persona_translator = "You are a precise literal translator."
        self.persona_editor = "You are an expert academic editor."
        
        self.terms: List[Dict[str, str]] = [] # [{'term': '...', 'translation': '...'}]
        self.semantic_segments: List[Dict[str, int]] = [] # [{"start": 0, "end": 10}, ...]

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Analyze input to generate Dual Personas, Extract Terms, and Semantic Segmentation.
        """
        logger.info("Initializing Academic Strategy Analysis...")
        handler = TSVHandler()
        try:
            rows = handler.read_file(input_file_path)
            if not rows:
                return

            # Snippet for analysis
            snippet_texts = [r.get('Source', '') for r in rows[:60]] # ~3-4k chars
            full_text = "\n".join(snippet_texts)[:8000]

            llm = LLMClient(self.config)
            preprocessing_model = self.get_model_for_stage('preprocessing')
            
            # 1. Generate Dual Personas
            self._generate_dual_personas(llm, full_text, preprocessing_model)
            
            # 2. Extract Terms
            if self.config.get('strategies', {}).get('academic', {}).get('extract_terms', True):
                term_model = self.get_model_for_stage('term_extraction')
                self._extract_terms(llm, full_text, term_model)

            # 3. Semantic Segmentation (Paragraph detection)
            self._generate_semantic_segments(llm, rows, preprocessing_model)

        except Exception as e:
            logger.error(f"Setup analysis failed: {e}")

    def _generate_semantic_segments(self, llm: LLMClient, rows: List[Dict[str, str]], model: str):
        """
        Divide the document into semantic paragraphs/sections for optimized batch processing.
        """
        logger.info("Generating semantic segments (Paragraphs)...")
        try:
            # Prepare numbered lines for LLM
            lines_text = ""
            for i, row in enumerate(rows[:300]): # Analyze first 300 rows to establish pattern (or full doc if small)
                source = row.get('Source', '')[:100].replace('\n', ' ')
                lines_text += f"{i}: {source}\n"
            
            prompt = f"""
            Analyze the following academic text rows and group them into Semantic Segments (Paragraphs).
            
            GUIDELINES:
            1. A "Segment" is a complete logical unit (e.g., a full paragraph, a section header + paragraph).
            2. Do NOT split a sentence or a paragraph across segments.
            3. Target segment size: 10-25 rows.
            4. If a paragraph is huge (>25 rows), split it at a logical full stop.
            
            INPUT TEXT:
            {lines_text}
            
            OUTPUT FORMAT (JSON Array):
            [
              {{"start": 0, "end": 15}},
              {{"start": 16, "end": 28}},
              ...
            ]
            Ensure all rows from 0 to {len(rows[:300])-1} are covered if possible.
            """
            
            response = llm.generate(prompt, model=model, response_mime_type="application/json")
            segments = json.loads(response)
            
            # Validate
            self.semantic_segments = []
            for seg in segments:
                if isinstance(seg, dict) and 'start' in seg and 'end' in seg:
                    self.semantic_segments.append({
                        "start": int(seg['start']),
                        "end": int(seg['end'])
                    })
            logger.info(f"✓ Generated {len(self.semantic_segments)} semantic segments.")
            
        except Exception as e:
            logger.warning(f"Semantic segmentation failed: {e}. Fallback to fixed batch size.")
            self.semantic_segments = []

    def get_batch_boundaries(self, total_rows: int) -> List[tuple]:
        """
        Return batch boundaries based on semantic segments.
        Falls back to fixed batch size if no segments available.
        """
        if self.semantic_segments:
            # Note: The LLM only analyzed the first N rows. If total_rows > N, we need a strategy.
            # For now, we use the segments we have, and then default batching for the rest.
            boundaries = [(s['start'], s['end'] + 1) for s in self.semantic_segments]
            
            last_end = boundaries[-1][1]
            if last_end < total_rows:
                # Fill the rest with fixed batch size
                batch_size = self.get_batch_size()
                for i in range(last_end, total_rows, batch_size):
                    boundaries.append((i, min(i + batch_size, total_rows)))
            
            return boundaries
        else:
            # Fallback to fixed processing
            batch_size = self.get_batch_size()
            return [(i, min(i + batch_size, total_rows)) for i in range(0, total_rows, batch_size)]

    def _generate_dual_personas(self, llm: LLMClient, text: str, model: str):
        prompt = f"""
        Analyze the provided text snippet from an academic paper.
        
        Step 1: Analysis
        Identify:
        1. The Academic Field (e.g., Inorganic Chemistry, Marxist Philosophy).
        2. The Register/Tone (e.g., highly technical, argumentative, descriptive).
        3. The Target Audience.
        4. The Author's Stance/Perspective.

        Step 2: Define Personas
        Based on the analysis, define TWO specific personas:

        1. **Literal Translator Persona**
           - Role: Transform Chinese text into an accurate, structurally faithful English draft.
           - Context Integration: Explicitly state the **Academic Field** and **Author's Stance** (from Step 1) in this description so the translator understands the source context. Do NOT include Target Audience or Target Tone here.
           - Key Directive: **Suppress any urge to polish, paraphrase, or improve flow.** Prioritize semantic precision and structural correspondence over idiomatic fluency. The goal is to create a transparent "semantic anchor" that reveals the original Chinese logic.
           - Tone: Objective, precise, unembellished, almost robotic.
           - Start with: "You are a specialized literal translator working on a paper in the field of [Insert Field] with a perspective of [Insert Stance]..."

        2. **Academic Editor (Proofreader) Persona**
           - Role: Refine the English draft for publication-level flow, clarity, and register.
           - Tone: Authoritative, polished, idiomatic.
           - Start with: "You are a senior editor..."
           - Crucial: The description of this persona MUST focus exclusively on English academic editing standards and conventions, without making any inferences or references to the original source language (e.g., Chinese, Spanish, Japanese, etc.).

        OUTPUT FORMAT (JSON):
        {{
          "analysis": "...",
          "literalTranslator": "...",
          "academicEditor": "..."
        }}
        
        TEXT:
        {text}
        """
        try:
            resp = llm.generate(prompt, model=model, response_mime_type="application/json")
            data = json.loads(resp)
            self.persona_translator = data.get('literalTranslator', self.persona_translator)
            self.persona_editor = data.get('academicEditor', self.persona_editor)
            logger.info("✓ Dual Personas generated.")
        except Exception as e:
            logger.warning(f"Persona generation failed: {e}")

    def _extract_terms(self, llm: LLMClient, text: str, model: str):
        prompt = f"""
        Extract top 20 recurring technical terms/concepts from this text.
        Output as JSON list of objects: {{ "term": "...", "translation": "..." }}
        Standardize translations to Chinese.

        TEXT:
        {text}
        """
        try:
            resp = llm.generate(prompt, model=model, response_mime_type="application/json")
            self.terms = json.loads(resp)
            logger.info(f"✓ Extracted {len(self.terms)} terms.")
        except Exception as e:
             logger.warning(f"Term extraction failed: {e}")

    def process_batch(
        self, 
        llm_client: LLMClient, 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: ContextWindowBuilder
    ) -> List[Dict[str, str]]:
        
        # Prepare Batch JSON using 'Source_Text' to be agnostic
        batch_input = [{
            'ID': r.get('ID'),
            'Source': r.get('Source'),
            'Draft': r.get('Target', '')
        } for r in batch_rows]
        
        term_text = "\n".join([f"- {t.get('term')}: {t.get('translation')}" for t in self.terms]) if self.terms else "None"
        
        # Prepare Context History (size from config)
        history_snippet = "None"
        window_config = self.get_context_window()
        history_size = window_config.get('before', 8)
        if history_rows:
            history_rows_data = history_rows[-history_size:]
            history_snippet = json.dumps([{
                'ID': r.get('ID'),
                'Target': r.get('Target')
            } for r in history_rows_data], indent=2, ensure_ascii=False)

        # Merge Protocol (Conditional based on config)
        merge_protocol = ""
        if self.should_enable_cross_row_merging():
            merge_protocol = """
        CRITICAL PROTOCOL: CROSS-ROW MERGING
        1. If a sentence is split across Row A and Row B:
           - MERGE them into a single coherent sentence in the Target.
           - Place the FULL translated sentence in Row A's Target.
           - Row B's Target MUST contain a placeholder: "[已向上合并]" (Merged into previous row).
        2. If Row A needs to be merged with Row B below:
           - Place the FULL translated sentence in Row B's Target.
           - Row A's Target MUST contain a placeholder: "[已向下合并]" (Merged into next row).
        3. ROW COUNT INVARIANCE:
           - You MUST return exactly the same number of rows as input.
        """
        
        prompt = f"""
        [ROLES]
        Phase 1 (Internal): {self.persona_translator}
        Phase 2 (Output): {self.persona_editor}
        *CRITICAL*: Phase 2 Editor must NOT look at the Source Language structure. Polish the English Draft into impeccable Chinese academic prose.
        
        [TERMINOLOGY]
        {term_text}
        
        [PREVIOUS CONTEXT (For Flow Continuity)]
        {history_snippet}
        
        [TASK]
        Translate/Polish the 'Source' into academic Chinese ('Target').
        Use the Draft if provided, but override it if imprecise.
        
        {merge_protocol}
        
        [INPUT DATA]
        {json.dumps(batch_input, indent=2)}
        
        [OUTPUT FORMAT]
        JSON Array of {{ "ID": "...", "Target": "..." }}
        """
        
        try:
            translation_model = self.get_model_for_stage('translation')
            response_text = llm_client.generate(
                prompt,
                model=translation_model,
                system_instruction="You are an automated academic publishing engine. Output strictly valid JSON.",
                response_mime_type="application/json"
            )
            results = json.loads(response_text)
            
            # Re-map results to preserve order and count
            processed = []
            result_map = {str(r.get('ID')): r.get('Target', '') for r in results}
            
            for row in batch_rows:
                rid = str(row['ID'])
                new_target = result_map.get(rid, row.get('Target', ''))
                
                processed.append({
                    'ID': row['ID'],
                    'Source': row['Source'],
                    'Target': new_target
                })
                
            # Perform QA Check (Conditional based on config)
            if self.should_enable_qa_check():
                processed = self.perform_qa(llm_client, processed, batch_rows)
            
            return processed
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return batch_rows

    def perform_qa(self, llm_client: LLMClient, processed_rows: List[Dict[str, str]], original_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Post-batch QA Check for Omissions, Misinterpretations, and Hallucinations.
        """
        qa_input = []
        for orig, proc in zip(original_rows, processed_rows):
            qa_input.append({
                'ID': orig.get('ID'),
                'Source': orig.get('Source'),
                'Revision': proc.get('Target')
            })
            
        prompt = f"""
        TASK: QA Check for CRITICAL translation errors ONLY. Identify:
        1. Omissions: SIGNIFICANT source information is COMPLETELY missing (not rephrased) in Revision.
        2. Misinterpretations: FACTUAL meaning is DIRECTLY contradicted (not stylistic rewording).
        3. Hallucinations: Substantial NEW information invented that has NO basis in Source.
        
        IMPORTANT - Do NOT flag as errors:
        - Stylistic changes (word order, punctuation, formal/informal style)
        - Minor rephrasing that preserves meaning
        - Adding/removing articles, conjunctions, or transitional words
        - Different but semantically equivalent translations
        - Formatting changes (quotation marks, spacing)
        - Author name transliteration differences (e.g., 派利夏恩 vs Pylyshyn)
        
        Focus ONLY on MAJOR FACTUAL errors that change the core meaning.
        
        INPUT:
        {json.dumps(qa_input, indent=2, ensure_ascii=False)}
        
        OUTPUT FORMAT (JSON):
        Array of objects: {{ "ID": "...", "Issue": "Description of issue or 'PASS'" }}
        Only include items with CRITICAL issues. If no critical issues, return empty array [].
        """
        
        try:
            qa_model = self.get_model_for_stage('qa_check')
            resp = llm_client.generate(prompt, model=qa_model, response_mime_type="application/json")
            issues = json.loads(resp)
            
            issue_map = {i.get('ID'): i.get('Issue') for i in issues if i.get('Issue') != 'PASS'}
            
            final_rows = []
            for row in processed_rows:
                rid = str(row.get('ID'))
                if rid in issue_map:
                    # Append QA Flag
                    row['Target'] += f" [[QA FLAG: {issue_map[rid]}]]"
                final_rows.append(row)
                
            return final_rows
            
        except Exception as e:
            logger.warning(f"QA Check failed: {e}")
            return processed_rows
