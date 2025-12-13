#!/usr/bin/env python3
"""
Unified Translator - Interactive Helper
A user-friendly CLI tool for configuring and running translation jobs.
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_banner():
    """Print welcome banner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🌐 UNIFIED TRANSLATOR - INTERACTIVE HELPER          ║
║                                                               ║
║   Strategies: Legal | Academic | Video                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

def get_file_path(prompt: str, must_exist: bool = True) -> str:
    """Get and validate a file path from user."""
    while True:
        path = input(f"\n{prompt}: ").strip()
        
        if not path:
            print("❌ Path cannot be empty. Please try again.")
            continue
            
        # Expand user paths like ~
        path = os.path.expanduser(path)
        
        if must_exist and not os.path.exists(path):
            print(f"❌ File not found: {path}")
            print("   Please enter a valid file path.")
            continue
            
        if must_exist and not path.endswith('.tsv'):
            print(f"⚠️  Warning: File does not have .tsv extension: {path}")
            confirm = input("   Continue anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                continue
                
        return path

def select_strategy() -> str:
    """Let user select translation strategy."""
    strategies = {
        '1': ('legal', '🏛️  Legal - Hong Kong law documents with CIL methodology'),
        '2': ('academic', '📚 Academic - Scholarly papers with dual-persona proofreading'),
        '3': ('video', '🎬 Video - Subtitles with transcription review and style guide')
    }
    
    print("\n📋 SELECT TRANSLATION STRATEGY:")
    print("-" * 50)
    for key, (_, desc) in strategies.items():
        print(f"  [{key}] {desc}")
    print("-" * 50)
    
    while True:
        choice = input("\nEnter strategy number (1-3): ").strip()
        if choice in strategies:
            return strategies[choice][0]
        print("❌ Invalid choice. Please enter 1, 2, or 3.")

def get_optional_params(strategy: str) -> dict:
    """Get optional parameters based on strategy."""
    params = {}
    
    print("\n⚙️  OPTIONAL SETTINGS:")
    print("-" * 50)
    
    # Glossary (for Legal)
    if strategy == 'legal':
        use_glossary = input("\n📖 Use a glossary file? (y/n, default: n): ").strip().lower()
        if use_glossary == 'y':
            params['glossary'] = get_file_path("Enter glossary TSV path")
    
    # Output file
    custom_output = input("\n📁 Custom output file path? (y/n, default: n): ").strip().lower()
    if custom_output == 'y':
        params['output'] = get_file_path("Enter output TSV path", must_exist=False)
    
    # Advanced: batch size
    custom_batch = input("\n🔢 Custom batch size? (y/n, default: n, recommended: 15): ").strip().lower()
    if custom_batch == 'y':
        while True:
            try:
                batch_size = int(input("   Enter batch size (5-50): ").strip())
                if 5 <= batch_size <= 50:
                    params['batch_size'] = batch_size
                    break
                print("❌ Batch size must be between 5 and 50.")
            except ValueError:
                print("❌ Please enter a valid number.")
    
    return params

def confirm_settings(input_file: str, strategy: str, params: dict) -> bool:
    """Display settings summary and confirm."""
    print("\n" + "=" * 60)
    print("📝 SETTINGS SUMMARY")
    print("=" * 60)
    print(f"  Input File:    {input_file}")
    print(f"  Strategy:      {strategy.upper()}")
    
    if 'output' in params:
        print(f"  Output File:   {params['output']}")
    else:
        base = os.path.splitext(input_file)[0]
        print(f"  Output File:   {base}_output.tsv (auto)")
    
    if 'glossary' in params:
        print(f"  Glossary:      {params['glossary']}")
    
    if 'batch_size' in params:
        print(f"  Batch Size:    {params['batch_size']}")
    
    print("=" * 60)
    
    confirm = input("\n🚀 Start translation? (y/n): ").strip().lower()
    return confirm == 'y'

def build_command(input_file: str, strategy: str, params: dict) -> list:
    """Build the command line arguments."""
    cmd = [sys.executable, 'main.py', input_file, '--mode', strategy]
    
    if 'output' in params:
        cmd.extend(['--output', params['output']])
    
    if 'glossary' in params:
        cmd.extend(['--glossary', params['glossary']])
    
    return cmd

def run_translation(input_file: str, strategy: str, params: dict):
    """Run the translation using main.py."""
    import subprocess
    
    cmd = build_command(input_file, strategy, params)
    
    print("\n" + "=" * 60)
    print("🔄 STARTING TRANSLATION...")
    print("=" * 60)
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        # Run the translation
        result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("✅ TRANSLATION COMPLETE!")
            print("=" * 60)
            
            # Show output location
            if 'output' in params:
                output_file = params['output']
            else:
                base = os.path.splitext(input_file)[0]
                output_file = f"{base}_output.tsv"
            
            print(f"\n📄 Output saved to: {output_file}")
        else:
            print("\n" + "=" * 60)
            print(f"❌ Translation failed with exit code: {result.returncode}")
            print("=" * 60)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Translation cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def interactive_mode():
    """Run the interactive helper."""
    print_banner()
    
    # Check for .env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        print("⚠️  Warning: .env file not found!")
        print("   Please create a .env file with your GEMINI_API_KEY")
        print("   Example: GEMINI_API_KEY=your_api_key_here")
        print()
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            return
    
    try:
        # Step 1: Get input file
        print("\n📂 STEP 1: SELECT INPUT FILE")
        print("-" * 50)
        print("Supported format: TSV (Tab-Separated Values)")
        print("Required columns: ID, Source, Target")
        input_file = get_file_path("Enter input TSV file path")
        
        # Step 2: Select strategy
        print("\n📋 STEP 2: SELECT STRATEGY")
        strategy = select_strategy()
        
        # Step 3: Optional parameters
        print("\n⚙️  STEP 3: CONFIGURE OPTIONS")
        params = get_optional_params(strategy)
        
        # Step 4: Confirm and run
        print("\n✅ STEP 4: CONFIRM AND RUN")
        if confirm_settings(input_file, strategy, params):
            run_translation(input_file, strategy, params)
        else:
            print("\n❌ Translation cancelled.")
            
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def quick_mode(args):
    """Quick mode with command line arguments."""
    print_banner()
    print("🚀 Quick Mode")
    print("-" * 50)
    
    params = {}
    if args.output:
        params['output'] = args.output
    if args.glossary:
        params['glossary'] = args.glossary
    
    if confirm_settings(args.input, args.mode, params):
        run_translation(args.input, args.mode, params)
    else:
        print("\n❌ Translation cancelled.")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Translator - Interactive Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode:  python helper.py
  Quick mode:        python helper.py -i input.tsv -m legal
  With glossary:     python helper.py -i input.tsv -m legal -g glossary.tsv
        """
    )
    
    parser.add_argument('-i', '--input', help='Input TSV file path')
    parser.add_argument('-m', '--mode', choices=['legal', 'academic', 'video'],
                        help='Translation strategy')
    parser.add_argument('-o', '--output', help='Output TSV file path (optional)')
    parser.add_argument('-g', '--glossary', help='Glossary TSV file path (optional)')
    
    args = parser.parse_args()
    
    # If input and mode provided, use quick mode
    if args.input and args.mode:
        if not os.path.exists(args.input):
            print(f"❌ Input file not found: {args.input}")
            sys.exit(1)
        quick_mode(args)
    else:
        # Interactive mode
        interactive_mode()

if __name__ == '__main__':
    main()
