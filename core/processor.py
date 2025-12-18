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
        
        # Determine Batches
        use_custom_boundaries = False
        batch_boundaries = []
        
        if hasattr(strategy, 'get_batch_boundaries') and callable(strategy.get_batch_boundaries):
            use_custom_boundaries = True
            batch_boundaries = strategy.get_batch_boundaries(len(raw_rows))
            total_batches = len(batch_boundaries)
        else:
            total_batches = math.ceil(len(raw_rows) / self.batch_size)
        
        # --- JOB SUMMARY & CONFIRMATION ---
        print("\n" + "="*50)
        print("🚀 JOB SUMMARY")
        print("="*50)
        print(f"📂 Input File:      {input_path}")
        print(f"💾 Output File:     {output_path}")
        print(f"🧠 Strategy:        {strategy.name}")
        print(f"📚 Glossary:        {getattr(strategy, 'glossary_path', '(None)')}") # Assuming we track this
        print(f"🎨 Style Guide:     {getattr(strategy, 'style_guide_path', '(None)')}")
        print(f"📊 Total Rows:      {len(raw_rows)}")
        print(f"📦 Est. Batches:    {total_batches}")
        print("="*50)
        
        try:
            input("\nPress Enter to start processing (or Ctrl+C to cancel)...")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return

        print("\nStarting processing...")
        start_time = time.time()
        
        # 3. Batch Loop
        if use_custom_boundaries:
            for batch_num, (start, end) in enumerate(batch_boundaries, 1):
                batch = raw_rows[start:end]
                
                print(f"⏳ Processing Batch {batch_num}/{total_batches} (Rows {start+1}-{end})...")
                logger.debug(f"Batch details: Start={start}, End={end}, Size={len(batch)}")
                
                try:
                    results = strategy.process_batch(
                        self.llm_client, 
                        batch, 
                        processed_rows, 
                        window_builder
                    )
                    
                    if len(results) != len(batch):
                        logger.error(f"Row count mismatch in batch {batch_num}. Expected {len(batch)}, got {len(results)}. Using fallback.")
                        results = batch
                    
                    processed_rows.extend(results)
                    
                except Exception as e:
                    logger.error(f"Batch {batch_num} failed: {e}")
                    processed_rows.extend(batch)
                
                time.sleep(0.5)
        else:
            # Original fixed batch_size loop
            for i in range(0, len(raw_rows), self.batch_size):
                batch_num = (i // self.batch_size) + 1
                batch = raw_rows[i : i + self.batch_size]
                
                print(f"⏳ Processing Batch {batch_num}/{total_batches} ({len(batch)} rows)...")
                
                try:
                    results = strategy.process_batch(
                        self.llm_client, 
                        batch, 
                        processed_rows, 
                        window_builder
                    )
                    
                    if len(results) != len(batch):
                        logger.error(f"Row count mismatch in batch {batch_num}. Using fallback.")
                        results = batch
                    
                    processed_rows.extend(results)
                    
                except Exception as e:
                    logger.error(f"Batch {batch_num} failed: {e}")
                    processed_rows.extend(batch)
                
                time.sleep(0.5)

        total_time = time.time() - start_time
        print(f"\n✅ Processing complete in {total_time:.2f}s")

        # 4. Write Output
        logger.info(f"Writing results to {output_path}")
        self.tsv_handler.write_file(output_path, processed_rows)
        logger.info("Processing complete.")
