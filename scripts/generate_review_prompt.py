import sys
import yaml
import os
from dotenv import load_dotenv

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm_client import LLMClient
from strategies.legal import LegalStrategy
from core.tsv_handler import TSVHandler # Needed for reading TSV to get rows for strategy.setup

def load_config(path: str) -> dict:
    if not os.path.exists(path):
        print(f"Config file not found at {path}. Using defaults.")
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def generate_prompt_from_strategy(input_tsv_path: str, glossary_path: str, style_guide_path: str):
    # 0. Load Environment
    load_dotenv(override=True)
    
    # 1. Load Config
    config = load_config("config.yaml") # Assuming config.yaml is in the root
    
    # Init LLM Client (even if not used for prompt generation, strategy setup might need it)
    try:
        llm_client = LLMClient(config) # This just checks API key presence
    except ValueError as e:
        print(f"Initialization Error: {e}")
        sys.exit(1)

    # 2. Instantiate Strategy
    strategy = LegalStrategy(config)
    
    # 3. Setup Context Files
    context_files = {
        'glossary': glossary_path,
        'style_guide': style_guide_path
    }
    
    # 4. Run Strategy Setup to generate CIL context
    print(f"Setting up LegalStrategy with {input_tsv_path} to generate CIL context...")
    strategy.setup(input_tsv_path, context_files)
    
    # 5. Generate and print the review prompt
    print("\n" + "="*50)
    print("✨ GENERATED EXTERNAL LLM REVIEW INSTRUCTION ✨")
    print("="*50 + "\n")
    print(strategy.get_external_review_prompt())
    print("\n" + "="*50)
    print("END OF INSTRUCTION")
    print("="*50 + "\n")

if __name__ == "__main__":
    # These paths are fixed for the current session based on the full test run
    input_file = "sample/tongwei_solar.tsv"
    glossary_file = "sample/glossary_legal.tsv"
    style_file = "sample/style_guide_legal.md"
    
    # Check if files exist
    if not os.path.exists(input_file):
        print(f"Error: Input TSV file not found at {input_file}")
        sys.exit(1)
    if not os.path.exists(glossary_file):
        print(f"Error: Glossary file not found at {glossary_file}")
        sys.exit(1)
    if not os.path.exists(style_file):
        print(f"Error: Style guide file not found at {style_file}")
        sys.exit(1)

    generate_prompt_from_strategy(input_file, glossary_file, style_file)
