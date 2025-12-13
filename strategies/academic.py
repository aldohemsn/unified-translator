"""
Academic Translation Strategy
Implements Dual-Persona (Translator + Editor) workflow with Cross-Row Merging and QA Check.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..core.llm_client import LLMClient
from ..core.context_window import ContextWindowBuilder
from ..core.tsv_handler import TSVHandler

logger = logging.getLogger(__name__)

class AcademicStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "AcademicStrategy"
        
        # Dual Personas
        self.persona_translator = "You are a precise literal translator."
        self.persona_editor = "You are an expert academic editor."
        
        self.terms: List[Dict[str, str]] = [] # [{'term': '...', 'translation': '...'}]

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Analyze input to generate Dual Personas and Extract Terms.
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
            persona_model = self.config.get('strategies', {}).get('academic', {}).get('persona_model', 'gemini-2.5-pro')
            
            # 1. Generate Dual Personas
            self._generate_dual_personas(llm, full_text, persona_model)
            
            # 2. Extract Terms
            if self.config.get('strategies', {}).get('academic', {}).get('extract_terms', True):
                self._extract_terms(llm, full_text, persona_model)

        except Exception as e:
            logger.error(f"Setup analysis failed: {e}")

    def _generate_dual_personas(self, llm: LLMClient, text: str, model: str):
        prompt = f"""
        Analyze the following academic text snippet (Field, Tone).
        
        Define TWO distinct personas:
        1. "Literal Translator": Focuses on semantic precision, suppresses urge to polish.
        2. "Academic Editor": Focuses on publication-level flow/register, blind to source typos.

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
        
        # Prepare Context History
        history_snippet = "None"
        if history_rows:
            history_rows_data = history_rows[-8:] # Last 8 rows
            history_snippet = json.dumps([{
                'ID': r.get('ID'),
                'Target': r.get('Target')
            } for r in history_rows_data], indent=2, ensure_ascii=False)

        # Merge Protocol Instruction
        merge_protocol = """
        CRITICAL PROTOCOL: CROSS-ROW MERGING
        1. If a sentence is split across Row A and Row B:
           - MERGE them into a single coherent sentence in the Target.
           - Place the FULL translated sentence in Row A's Target.
           - STRICTLY leave Row B's Target as an empty string ("").
        2. ROW COUNT INVARIANCE:
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
            response_text = llm_client.generate(
                prompt,
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
                
            # Perform QA Check
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
        TASK: QA Check. Identify:
        1. Omissions (Source info missing in Revision).
        2. Misinterpretations (Meaning contradicted).
        3. Hallucinations (Added info not in Source).
        
        Ignore stylistic changes. Focus on FACTUAL errors.
        
        INPUT:
        {json.dumps(qa_input, indent=2, ensure_ascii=False)}
        
        OUTPUT FORMAT (JSON):
        Array of objects: {{ "ID": "...", "Issue": "Description of issue or 'PASS'" }}
        Only include items with issues.
        """
        
        try:
            resp = llm_client.generate(prompt, response_mime_type="application/json")
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
