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
        self.persona = "You are an expert academic editor."
        self.terms = [] # List of strings or dicts

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Analyze input file to generate persona and terms.
        """
        logger.info("Initializing Academic Strategy Analysis...")
        handler = TSVHandler()
        try:
            # Read first N rows for analysis
            rows = handler.read_file(input_file_path)
            if not rows:
                return

            # Construct a snippet
            snippet_texts = [r.get('Source', '') for r in rows[:50]] # First 50 rows
            full_text = "\n".join(snippet_texts)[:8000] # Cap at 8k chars

            # We need an LLM client for setup phase. 
            # In a real app, we might pass it or instantiate a temporary one.
            # Here we instantiate one based on config.
            llm = LLMClient(self.config)
            
            # 1. Generate Persona
            self._generate_persona(llm, full_text)
            
            # 2. Extract Terms (if configured)
            if self.config.get('strategies', {}).get('academic', {}).get('extract_terms', True):
                self._extract_terms(llm, full_text)

        except Exception as e:
            logger.error(f"Setup analysis failed: {e}")
            logger.info("Falling back to default persona.")

    def _generate_persona(self, llm: LLMClient, text: str):
        prompt = f"""
        Analyze the following academic text snippet.
        Identify: Field, Tone, Author's Stance.
        
        Output a "Persona Description" for an Academic Editor who will polish this text.
        The persona must be 1-2 sentences, defining the role and tone.
        
        Text:
        {text}
        """
        try:
            self.persona = llm.generate(prompt).strip()
            logger.info(f"Generated Persona: {self.persona}")
        except Exception as e:
            logger.warning(f"Persona generation failed: {e}")

    def _extract_terms(self, llm: LLMClient, text: str):
        prompt = f"""
        Extract top 10 key technical terms from this academic text.
        Return as a JSON list of strings.
        
        Text:
        {text}
        """
        try:
            resp = llm.generate(prompt, response_mime_type="application/json")
            self.terms = json.loads(resp)
            logger.info(f"Extracted {len(self.terms)} terms.")
        except Exception as e:
             logger.warning(f"Term extraction failed: {e}")

    def process_batch(
        self, 
        llm_client: LLMClient, 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: ContextWindowBuilder
    ) -> List[Dict[str, str]]:
        
        # Prepare Batch JSON
        # Map Source to 'Source_Text' to be agnostic
        batch_input = [{
            'ID': r.get('ID'),
            'Source_Text': r.get('Source'),
            'Draft': r.get('Target', '') # Might be empty if pure proofreading
        } for r in batch_rows]
        
        terminology_text = ", ".join(self.terms) if self.terms else "None"
        
        prompt = f"""
        [PROJECT PERSONA]
        {self.persona}
        
        [TERMINOLOGY]
        {terminology_text}
        
        TASK:
        Refine the 'Draft' English text based on the 'Source_Text'. 
        If 'Draft' is empty, Translate 'Source_Text' directly.
        
        CONSTRAINTS:
        1. Academic Rigor: Maintain high formal register.
        2. Structure: Return EXACTLY the same number of rows.
        3. Output JSON Array.
        
        INPUT:
        {json.dumps(batch_input, indent=2)}
        
        OUTPUT FORMAT:
        JSON Array of {{ "ID": "...", "Target": "..." }}
        """
        
        try:
            response_text = llm_client.generate(
                prompt,
                response_mime_type="application/json"
            )
            results = json.loads(response_text)
            
            # Map back
            processed_map = {r.get('ID'): r.get('Target') for r in results}
            
            output = []
            for row in batch_rows:
                row_id = row['ID']
                new_target = processed_map.get(row_id, row.get('Target', ''))
                
                output.append({
                    'ID': row_id,
                    'Source': row['Source'],
                    'Target': new_target
                })
            return output
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return batch_rows
