"""
Video Translation Strategy
Implements Transcription Audit, Style Guide generation, and VO/OS separation.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from .base_strategy import BaseStrategy
from core.llm_client import LLMClient
from core.context_window import ContextWindowBuilder
from core.tsv_handler import TSVHandler

logger = logging.getLogger(__name__)

class VideoStrategy(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "VideoStrategy"
        self._strategy_config = self._get_strategy_config('video')
        self.style_guide = "No specific style guide generated."
        self.transcript_context = "" # Global context storage

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Generate Compressed Context Summary and Detailed Style Guide.
        """
        handler = TSVHandler()
        try:
            rows = handler.read_file(input_file_path)
            if not rows:
                return

            # 1. Generate Compressed Context (replaces raw transcript storage)
            if self.should_inject_full_context():
                full_text = " ".join([r.get('Source', '') for r in rows[:500]])
                self._generate_compressed_context(full_text)
            
            # 2. Generate Style Guide
            if self._strategy_config.get('generate_style_guide', True):
                llm = LLMClient(self.config)
                style_snippet = " ".join([r.get('Source', '') for r in rows[:200]])
                self._generate_detailed_style_guide(llm, style_snippet)

        except Exception as e:
            logger.warning(f"Video Setup failed: {e}")
    
    def _generate_compressed_context(self, full_text: str) -> None:
        """
        Compress full transcript into structured summary.
        Reduces token usage from ~3000 to ~500 while preserving key context.
        """
        logger.info("Generating compressed context summary...")
        
        try:
            llm = LLMClient(self.config)
            
            compress_prompt = f"""为以下视频字幕生成【场景摘要】，用于指导翻译。

请包含：
1. **主题**: 视频在讲什么（一句话）
2. **说话人**: 有哪些角色/身份（如：主持人、嘉宾A、旁白）
3. **语境**: 正式/口语，新闻/教程/剧情/采访
4. **关键术语**: 专有名词、人名、品牌名（列出 5-10 个）
5. **特殊注意**: 任何翻译时需要注意的点

字幕原文（前 5000 字符）：
{full_text[:5000]}

输出格式（中文，控制在 500 字以内）：
"""
            
            response = llm.generate(compress_prompt)
            if response:
                self.transcript_context = response.strip()
                logger.info(f"✓ Compressed context generated ({len(self.transcript_context)} chars, down from {len(full_text[:self.get_full_context_max_chars()])})")
            else:
                # Fallback to truncated raw text
                self.transcript_context = full_text[:1000]
                
        except Exception as e:
            logger.warning(f"Context compression failed: {e}. Using truncated raw text.")
            self.transcript_context = full_text[:1000]

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
        window_config = self.get_context_window()
        history_size = window_config.get('before', 5)
        if history_rows:
             history_snippet = json.dumps([{
                 'English': r.get('Source'),
                 'Chinese': r.get('Target')
             } for r in history_rows[-history_size:]], indent=2, ensure_ascii=False)

        # Translationese Blacklist (from config or default)
        blacklist_terms = self.get_blacklist_terms()
        if blacklist_terms:
            blacklist_lines = [f"- Do NOT use \"{term}\"" for term in blacklist_terms]
            blacklist_instruction = "**NEGATIVE CONSTRAINTS (Translationese Blacklist)**:\n" + "\n".join(blacklist_lines)
        else:
            blacklist_instruction = ""

        prompt = f"""
        [STYLE GUIDE]
        {self.style_guide}
        
        {blacklist_instruction}
        
        [SCENE SUMMARY (Compressed Context)]
        {self.transcript_context}
        
        [PREVIOUS CONTEXT]
        {history_snippet}
        
        [TASK]
        1. **Transcription Audit**: Check 'English' source for typos, ASR errors (homophones), or wrong names.
           - Protocol: If error found, PREPEND "⚠️ [TRANSCRIPTION FLAG]: <Note>" to 'Comments'.
        2. **Translation**:
           - Determine if segment is VO (Spoken) or OS (Text).
           - Apply appropriate style (VO=Fluid, OS=Concise).
        
        [INPUT DATA]
        {json.dumps(formatted_batch, indent=2, ensure_ascii=False)}
        
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
