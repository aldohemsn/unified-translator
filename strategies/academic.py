"""
Academic Translation Strategy
Implements Dual-Persona (Translator + Editor) workflow with Cross-Row Merging.
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
        
        # Two-Pass Workflow: 
        # But for efficiency/integration with current Single-Pass loop (Processor),
        # we can combine them into a powerful Single-Pass Prompt 
        # OR run them internally here. 
        # Given "Cross-Row Merging" requirement, Single-Pass with clear instructions is usually better 
        # to avoid alignment hell between passes.
        
        # Let's effectively use the "Academic Editor" persona but feed it the "Literal" needs as constraints.
        
        batch_input = [{
            'ID': r.get('ID'),
            'Source': r.get('Source'),
            'Draft': r.get('Target', '')
        } for r in batch_rows]
        
        term_text = "\n".join([f"- {t.get('term')}: {t.get('translation')}" for t in self.terms]) if self.terms else "None"
        
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
        
        [TERMINOLOGY]
        {term_text}
        
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
                
            # Optional: QA Check (Sampling or Batch)
            # self.perform_qa(llm_client, processed)
            
            return processed
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return batch_rows

    def perform_qa(self, llm_client: LLMClient, processed_rows: List[Dict[str, str]]):
        """
        Optional post-batch QA. currently a stub or can be called if needed.
        """
        # Implementation for checking Omissions/Hallucinations
        pass
