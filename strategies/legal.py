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
        self.glossary = {}
        self.context_note = "Legal Translation Context (General)"

    def setup(self, input_file_path: str, context_files: Dict[str, str] = None) -> None:
        """
        Load glossary and set context.
        """
        if context_files and 'glossary' in context_files:
            glossary_path = context_files['glossary']
            self._load_glossary(glossary_path)
            
        # TODO: Implement optional LLM-based context generation (CIL) here if needed
        # For now, we rely on the generic context or arguments

    def _load_glossary(self, path: str):
        if not os.path.exists(path):
            logger.warning(f"Glossary file not found: {path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                # Detect header
                f_start = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                has_header = sniffer.has_header(f_start)
                
                reader = csv.reader(f, delimiter='\t')
                if has_header:
                     # Skip header if it looks like one, or just treat first row as data if it's Term/Translation
                     # A simple heuristic: if row[0].lower() == 'english' or 'term', skip
                     first_row = next(reader, None)
                     if first_row and first_row[0].lower() not in ['english', 'term', 'source']:
                         self.glossary[first_row[0].strip()] = first_row[1].strip()
                
                for row in reader:
                    if len(row) >= 2:
                        self.glossary[row[0].strip()] = row[1].strip()
            
            logger.info(f"Loaded {len(self.glossary)} terms from glossary.")
        except Exception as e:
            logger.error(f"Error loading glossary: {e}")

    def _build_glossary_prompt(self) -> str:
        if not self.glossary:
            return "No mandatory glossary provided."
        
        lines = ["MANDATORY GLOSSARY (ABSOLUTE REQUIREMENT):"]
        for k, v in self.glossary.items():
            lines.append(f"- {k} -> {v}")
        return "\n".join(lines)

    def _enforce_glossary(self, source: str, target: str) -> str:
        """
        Post-LLM compliance check.
        """
        violations = []
        for term_en, term_cn in self.glossary.items():
            if term_en in source:
                # Handle alternatives separated by /
                options = [opt.strip() for opt in term_cn.split('/')]
                if not any(opt in target for opt in options):
                    # Flag violation
                    violations.append(f"{term_en} should be {term_cn}")
        
        if violations:
            target += f" [[GLOSSARY VIOLATION: {'; '.join(violations)}]]"
        
        return target

    def process_batch(
        self, 
        llm_client: LLMClient, 
        batch_rows: List[Dict[str, str]], 
        history_rows: List[Dict[str, str]],
        window_builder: ContextWindowBuilder
    ) -> List[Dict[str, str]]:
        
        # We process legal texts often row-by-row for precision, 
        # or in small batches. The CIL prompt is heavy.
        # Let's use a batch prompt but ask for individual handling.
        
        processed_batch = []
        glossary_text = self._build_glossary_prompt()
        
        # NOTE: For Legal, we construct a prompt PER ROW effectively if we use context window effectively 
        # in a sliding manner. But `process_batch` implies we want to send multiple rows to the LLM.
        # In the original `legal-translation-cil`, it was sliding window per row (or small groups).
        # Let's stick to the prompt structure which processes the batch.
        
        # Prepare Batch Data for Prompt
        batch_input_str = json.dumps([{k: v for k,v in r.items() if k in ['ID', 'Source', 'Target']} for r in batch_rows], indent=2)
        
        prompt = f"""
        You are a legal translation expert specializing in Hong Kong law.
        
        CONTEXT NOTE: {self.context_note}
        
        {glossary_text}
        
        TASK:
        Review and refine the following translations.
        
        REQUIREMENTS:
        1. STRICTLY follow the Glossary. If source has a glossary term, target MUST use the defined Chinese translation.
        2. Maintain Format: Output must be a stable JSON array.
        3. Logic: Ensure legal precision and logical flow.
        
        INPUT DATA:
        {batch_input_str}
        
        OUTPUT FORMAT:
        JSON Array of objects: {{ "ID": "...", "Source": "...", "Target": "..." }}
        """

        response_schema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "ID": {"type": "STRING"},
                    "Source": {"type": "STRING"},
                    "Target": {"type": "STRING"}
                },
                "required": ["ID", "Source", "Target"]
            }
        }

        try:
            response_text = llm_client.generate(
                prompt, 
                system_instruction="You are a legal translator engine. Output strictly valid JSON.",
                response_schema=response_schema,
                response_mime_type="application/json"
            )
            
            results = json.loads(response_text)
            
            # Post-process and Enforce Glossary
            # Create a map for quick lookup
            result_map = {r.get('ID'): r.get('Target', '') for r in results}
            
            for row in batch_rows:
                row_id = row['ID']
                original_target = row['Target']
                new_target = result_map.get(row_id, original_target)
                
                # Enforce
                final_target = self._enforce_glossary(row['Source'], new_target)
                
                processed_batch.append({
                    'ID': row_id,
                    'Source': row['Source'],
                    'Target': final_target
                })
                
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Fallback: return original
            return batch_rows

        return processed_batch
