"""
Video Translation Strategy
Implements Transcription Audit, Style Guide generation, and VO/OS separation.
"""
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
        Generate Detailed Style Guide (VO vs OS, Tone).
        """
        if self.config.get('strategies', {}).get('video', {}).get('generate_style_guide', True):
            handler = TSVHandler()
            try:
                rows = handler.read_file(input_file_path)
                if rows:
                    # Larger snippet for video context
                    transcript_snippet = " ".join([r.get('Source', '') for r in rows[:300]]) 
                    llm = LLMClient(self.config)
                    self._generate_detailed_style_guide(llm, transcript_snippet)
            except Exception as e:
                logger.warning(f"Style guide generation failed: {e}")

    def _generate_detailed_style_guide(self, llm: LLMClient, text: str):
        prompt = f"""
        You are a Senior Localization Architect for Video Content.
        Task: Create a "Best Efficient Style Guide".
        
        Sections Required:
        1. **Project Context**: Topic, Vibe (e.g., Casual YouTube vs. Formal Doc).
        2. **Stylistic Protocols**:
           - **Voice-Over (VO)**: Guidelines for spoken narrative (fluidity, breath).
           - **On-Screen Text (OS)**: Guidelines for titles/labels (conciseness, nominal style).
        3. **Formatting**: Rules for numbers, punctuation in subtitles.
        
        Source Text Snippet:
        {text[:5000]}
        """
        try:
            val = llm.generate(prompt)
            if val:
                self.style_guide = val
            logger.info("✓ Video Style Guide generated.")
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
            
        history_snippet = "None"
        if history_rows:
             history_snippet = json.dumps([{
                 'English': r.get('Source'),
                 'Chinese': r.get('Target')
             } for r in history_rows[-5:]], indent=2)

        # Translationese Blacklist
        blacklist_instruction = """
        **NEGATIVE CONSTRAINTS (Translationese Blacklist)**:
        - Do NOT use "进行" (conduct) as a dummy verb.
        - Do NOT use "通过" (via/through) for 'by'.
        - Do NOT use "旨在" (aim to).
        - Avoid "它" (it) unless referring to a specific physical object.
        """

        prompt = f"""
        [STYLE GUIDE]
        {self.style_guide}
        
        {blacklist_instruction}
        
        [PREVIOUS CONTEXT]
        {history_snippet}
        
        [TASK]
        1. **Transcription Audit**: Check 'English' source for typos, ASR errors (homophones), or wrong names.
           - Protocol: If error found, PREPEND "⚠️ [TRANSCRIPTION FLAG]: <Note>" to 'Comments'.
        2. **Translation**:
           - Determine if segment is VO (Spoken) or OS (Text).
           - Apply appropriate style (VO=Fluid, OS=Concise).
        
        [INPUT DATA]
        {json.dumps(formatted_batch, indent=2)}
        
        [OUTPUT FORMAT]
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
                
                new_target = res.get('Chinese_Proofread', row.get('Target', ''))
                comments = res.get('Comments', '')
                
                # Append to existing comments if any
                if row.get('Comments'):
                    comments = f"{row.get('Comments')} | {comments}" if comments else row.get('Comments')

                output.append({
                    'ID': row_id,
                    'Source': row['Source'],
                    'Target': new_target,
                    'Comments': comments
                })
            return output

        except Exception as e:
            logger.error(f"Video batch processing failed: {e}")
            return [{**r, 'Comments': f"Error: {e}"} for r in batch_rows]
