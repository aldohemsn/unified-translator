import json
import logging
from typing import List, Dict, Any, Optional
from .base_strategy import BaseStrategy
from ..core.llm_client import LLMClient
from ..core.context_window import ContextWindowBuilder
from ..core.tsv_handler import TSVHandler

logger = logging.getLogger(__name__)

class VideoStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "VideoStrategy"
        self.style_guide = "No specific style guide generated."

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Generate Style Guide from transcript if possible.
        """
        if self.config.get('strategies', {}).get('video', {}).get('generate_style_guide', True):
            handler = TSVHandler()
            try:
                rows = handler.read_file(input_file_path)
                if rows:
                    transcript_snippet = " ".join([r.get('Source', '') for r in rows[:200]]) # First 200 lines
                    llm = LLMClient(self.config)
                    self._generate_style_guide(llm, transcript_snippet)
            except Exception as e:
                logger.warning(f"Style guide generation failed: {e}")

    def _generate_style_guide(self, llm: LLMClient, text: str):
        prompt = f"""
        Analyze the following video transcript snippet.
        Generate a Style Guide (Tone, VO vs OS rules).
        
        Text:
        {text}
        """
        try:
            val = llm.generate(prompt)
            if val:
                self.style_guide = val
            logger.info("Style Guide validated.")
        except Exception:
            pass

    def process_batch(
        self, 
        llm_client: LLMClient, 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: ContextWindowBuilder
    ) -> List[Dict[str, str]]:
        
        # Prepare Batch
        formatted_batch = []
        for r in batch_rows:
            formatted_batch.append({
                'ID': r.get('ID'),
                'English': r.get('Source'),
                'Chinese': r.get('Target', '')
            })
            
        # Prepare History (last 5 processed rows)
        history_snippet = "None"
        if history_rows:
             history_snippet = json.dumps([{
                 'English': r.get('Source'),
                 'Chinese_Proofread': r.get('Target')
             } for r in history_rows[-5:]], indent=2)

        prompt = f"""
        [STYLE GUIDE]
        {self.style_guide}
        
        [PREVIOUS CONTEXT]
        {history_snippet}
        
        TASK:
        1. Proofread the 'Chinese' translation against 'English' source.
        2. AUDIT the 'English' source for ASR/Transcription errors (e.g. "Elan Musk" -> "Elon Musk").
           - If a Transcription Error is found, prepend "⚠️ [TRANSCRIPTION FLAG]" to the 'Comments' field.
        3. Output JSON Array.
        
        INPUT DATA:
        {json.dumps(formatted_batch, indent=2)}
        
        OUTPUT FORMAT:
        JSON Array of {{ "ID": "...", "Chinese_Proofread": "...", "Comments": "..." }}
        """
        
        try:
            response_text = llm_client.generate(
                prompt,
                response_mime_type="application/json"
            )
            results = json.loads(response_text)
            
            result_map = {r.get('ID'): r for r in results}
            
            output = []
            for row in batch_rows:
                row_id = row['ID']
                res = result_map.get(row_id, {})
                
                # Combine original target if proofread missing? No, replace.
                new_target = res.get('Chinese_Proofread', row.get('Target', ''))
                comments = res.get('Comments', '')
                
                output.append({
                    'ID': row_id,
                    'Source': row['Source'],
                    'Target': new_target,
                    'Comments': comments
                })
            return output

        except Exception as e:
            logger.error(f"Video batch processing failed: {e}")
            # Return original with error note
            return [{**r, 'Comments': f"Error: {e}"} for r in batch_rows]
