import logging
import math
import time
from typing import List, Dict, Any, Optional

from .tsv_handler import TSVHandler
from .llm_client import LLMClient
from .context_window import ContextWindowBuilder

logger = logging.getLogger(__name__)

class Processor:
    def __init__(self, config: Dict[str, Any], llm_client: LLMClient):
        self.config = config
        self.llm_client = llm_client
        self.tsv_handler = TSVHandler()
        self.batch_size = config.get('processing', {}).get('batch_size', 15)

    def run(self, input_path: str, output_path: str, strategy: 'Any'):
        """
        Main processing loop.
        """
        logger.info(f"Starting processing for {input_path} with strategy {strategy.name}")
        
        # 1. Read Data
        raw_rows = self.tsv_handler.read_file(input_path)
        logger.info(f"Loaded {len(raw_rows)} rows.")
        
        if not raw_rows:
            logger.warning("Empty input file.")
            return

        # 2. Setup Context Window
        window_builder = ContextWindowBuilder(
            raw_rows,
            window_before=self.config.get('processing', {}).get('context_window', {}).get('before', 3),
            window_after=self.config.get('processing', {}).get('context_window', {}).get('after', 2)
        )
        
        processed_rows = []
        
        # 3. Batch Loop
        total_batches = math.ceil(len(raw_rows) / self.batch_size)
        
        for i in range(0, len(raw_rows), self.batch_size):
            batch_num = (i // self.batch_size) + 1
            batch = raw_rows[i : i + self.batch_size]
            
            logger.info(f"Processing Batch {batch_num}/{total_batches} ({len(batch)} rows)...")
            
            try:
                # Call Strategy
                # Using processed_rows as history
                results = strategy.process_batch(
                    self.llm_client, 
                    batch, 
                    processed_rows, 
                    window_builder
                )
                
                # Verify Row Invariance
                if len(results) != len(batch):
                    logger.error(f"Row count mismatch in batch {batch_num}. Expected {len(batch)}, got {len(results)}. Using fallback.")
                    # Fill missing or truncate? 
                    # Ideally strategy handles this, but if not, we must preserve alignment.
                    # Fallback: append original batch if mismatch
                    results = batch
                
                processed_rows.extend(results)
                
                # Optional: Autosave / Streaming write could go here
                
            except Exception as e:
                logger.error(f"Batch {batch_num} failed completely: {e}")
                processed_rows.extend(batch) # Fallback to original
            
            # Rate limit / Politeness
            time.sleep(0.5)

        # 4. Write Output
        logger.info(f"Writing results to {output_path}")
        self.tsv_handler.write_file(output_path, processed_rows)
        logger.info("Processing complete.")
