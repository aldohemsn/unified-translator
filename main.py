import argparse
import logging
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from dotenv import load_dotenv

from core.llm_client import LLMClient
from core.processor import Processor
from strategies.academic import AcademicStrategy
from strategies.legal import LegalStrategy
from strategies.video import VideoStrategy

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("UnifiedTranslator")

def load_config(path: str) -> dict:
    if not os.path.exists(path):
        logger.warning(f"Config file not found at {path}. Using defaults.")
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Unified Translation Framework")
    parser.add_argument("input", help="Input TSV file path")
    parser.add_argument("--output", help="Output TSV file path (default: input_processed.tsv)")
    parser.add_argument("--mode", required=True, choices=['academic', 'legal', 'video'], help="Translation strategy")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--glossary", help="Path to glossary TSV (for Legal mode)")
    
    args = parser.parse_args()
    
    # 0. Load Environment
    load_dotenv(override=True)
    
    # 1. Load Config
    config = load_config(args.config)
    
    # Debug: Check API Key
    key_var = config.get('llm', {}).get('api_key_env_var', 'GEMINI_API_KEY')
    api_key = os.getenv(key_var)
    if api_key:
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        logger.info(f"Loaded API Key from '{key_var}': {masked_key} (Length: {len(api_key)})")
    else:
        logger.error(f"FAILED to load API Key from '{key_var}'")

    # 2. Init LLM Client
    try:
        llm_client = LLMClient(config)
    except ValueError as e:
        logger.error(f"Initialization Error: {e}")
        sys.exit(1)

    # 3. Select Strategy
    strategy_map = {
        'academic': AcademicStrategy,
        'legal': LegalStrategy,
        'video': VideoStrategy
    }
    
    StrategyClass = strategy_map[args.mode]
    strategy = StrategyClass(config)
    
    # 4. Prepare Context Files
    context_files = {}
    if args.glossary:
        context_files['glossary'] = args.glossary
        
    # 5. Run Setup
    logger.info(f"Setting up {args.mode} strategy...")
    strategy.setup(args.input, context_files)
    
    # 6. Run Processing
    processor = Processor(config, llm_client)
    output_path = args.output
    if not output_path:
        base, ext = os.path.splitext(args.input)
        output_path = f"{base}_processed{ext}"
        
    processor.run(args.input, output_path, strategy)

if __name__ == "__main__":
    main()
