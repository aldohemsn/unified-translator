# Unified Translator

A unified translation framework supporting multiple strategies for different content types.

## 🚀 Quick Start

### Interactive Mode (Recommended for beginners)

```bash
python helper.py
```

This will guide you through:
1. Selecting your input TSV file
2. Choosing a translation strategy
3. Configuring optional settings
4. Running the translation

### Quick Mode

```bash
# Legal translation
python helper.py -i input.tsv -m legal

# Academic proofreading
python helper.py -i input.tsv -m academic

# Video subtitle translation
python helper.py -i input.tsv -m video
```

### Direct CLI

```bash
python main.py input.tsv --mode legal --output output.tsv
```

## 📋 Translation Strategies

| Strategy | Use Case | Features |
|----------|----------|----------|
| **Legal** | Legal documents (contracts, judgments, regulations) | CIL methodology, Glossary enforcement |
| **Academic** | Scholarly papers | Dual-persona proofreading, QA checks |
| **Video** | Subtitles/Transcripts | Style guide, Translationese detection |

## 📂 Input Format

TSV file with columns:
- `ID` - Unique identifier for each row
- `Source` - Source text
- `Target` - *(Optional)* Pre-translated text for proofreading mode

**Two modes:**
- **Translation mode**: If `Target` column is missing or empty → translate from scratch
- **Proofreading mode**: If `Target` has content → review and improve existing translation

Example (Translation mode):
```
ID	Source
1	Hello world
2	Good morning
```

Example (Proofreading mode):
```
ID	Source	Target
1	Hello world	你好世界
2	Good morning	早上好
```

## ⚙️ Configuration

Edit `config.yaml` to customize:
- LLM model selection
- Batch size
- Context window size
- Strategy-specific options

## 🔑 API Setup

1. Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_api_key_here
```

2. Or set environment variable:
```bash
export GEMINI_API_KEY=your_api_key_here
```

## 📦 Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 📁 Project Structure

```
unified-translator/
├── main.py                  # Main entry point
├── helper.py                # Interactive helper
├── config.yaml              # Configuration
├── requirements.txt         # Dependencies
├── README.md
│
├── core/                    # Core modules
│   ├── llm_client.py        # LLM API client
│   ├── processor.py         # Batch processor
│   ├── tsv_handler.py       # TSV I/O
│   └── context_window.py    # Sliding window builder
│
├── strategies/              # Translation strategies
│   ├── base_strategy.py     # Base class
│   ├── legal.py             # Legal strategy (CIL)
│   ├── academic.py          # Academic strategy (Dual-Persona)
│   └── video.py             # Video strategy (Context-Aware)
│
├── docs/                    # 📚 Documentation
│   ├── METHODOLOGY.md       # Translation methodology whitepaper
│   ├── SPECIFICATIONS.md    # System specifications
│   ├── ROADMAP.md           # Development roadmap
│   ├── MODEL_TOKEN_ANALYSIS.md
│   ├── VIDEO_TRANSLATION_LOGIC_EXPLAINED.md
│   └── ACADEMIC_STRATEGY_EXPLAINED.md
│
├── scripts/                 # 🔧 Utility scripts
│   ├── docx/                # DOCX processing tools
│   │   ├── extract_docx_to_tsv.py
│   │   ├── extract_glossary_table.py
│   │   ├── tsv_to_docx.py
│   │   └── compare_docx.py
│   ├── qa/                  # Quality assurance tools
│   │   ├── check_compliance.py
│   │   └── check_locked.py
│   ├── apply_client_format.py
│   └── generate_review_prompt.py
│
├── tests/                   # 🧪 Test fixtures
│   ├── test_academic.tsv
│   ├── test_legal.tsv
│   └── test_video.tsv
│
└── logs/                    # 📝 Development logs (archived)
    └── SUMMARY_*.md
```

## 📊 Output

Output TSV file contains:
- Original `ID` and `Source` columns
- Updated `Target` column with translations
- Strategy-specific columns (e.g., `Comments` for video)

## License

MIT
