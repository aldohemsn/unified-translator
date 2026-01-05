# Unified Translator System Specifications

**Version:** 1.0 (As-Is)
**Date:** 2025-12-13

## 1. System Overview

The **Unified Translator** is a Python-based framework designed to provide specialized translation strategies for different content domains (Legal, Academic, Video). It leverages Large Language Models (LLMs) via the Google Gemini API to perform context-aware translation, proofreading, and quality assurance.

The system is built on a modular architecture where a central `Processor` orchestrates the workflow, delegating domain-specific logic to interchangeable `Strategy` classes.

## 2. Architecture

### 2.1 Core Components

*   **`main.py`**: The entry point. Handles argument parsing, configuration loading, and strategy initialization.
*   **`helper.py`**: An interactive CLI wizard that simplifies configuration and execution for end-users.
*   **`config.yaml`**: Centralized configuration file for LLM settings, global defaults, and per-strategy parameters.
*   **`core/processor.py`**: Manages the batch processing loop, sliding context window construction, and file I/O.
*   **`core/llm_client.py`**: A wrapper around the `google-genai` library, handling API authentication, retries, and model selection.
*   **`core/tsv_handler.py`**: Utilities for reading and writing TSV (Tab-Separated Values) files, ensuring data integrity.
*   **`strategies/base_strategy.py`**: Abstract base class defining the contract for all strategies (`setup` and `process_batch`).

### 2.2 Data Flow

1.  **Input**: The system accepts a TSV file (`ID`, `Source`, `Target`) and optional configuration overrides.
2.  **Initialization**: The selected `Strategy` performs a setup phase (e.g., analyzing the full document, generating a persona).
3.  **Batch Processing**:
    *   The `Processor` chunks input rows into batches (configurable size).
    *   For each batch, a sliding window of context (previous rows) is constructed.
    *   The `Strategy` receiving the batch + context constructs a prompt and calls the LLM.
4.  **Post-Processing**: The `Strategy` applies necessary checks (QA, glossary enforcement) and formatting.
5.  **Output**: Results are written line-by-line or batch-by-batch to an output TSV file.

## 3. Translation Strategies

### 3.1 Legal Strategy (`strategies/legal.py`)
*   **Target Domain**: Hong Kong Legal Documents (Judgments, Contracts).
*   **Methodology**: **CIL (Context-Insight-Logic)**.
    *   **Context**: Generates a high-level summary of the case/document.
    *   **Insight**: Explains key legal terms and Hong Kong specific procedural rules.
    *   **Logic (Layman's)**: Explains complex sentences using Feynman's technique before translation.
*   **Key Features**:
    *   **Strict Output**: Enforces pure translation output without analysis/commentary in the final result.
    *   **Glossary Enforcement**: Strict checking against a provided glossary.
    *   **Processing**: Row-by-row (Batch size: 1) for maximum precision.
    *   **Context Window**: Small (3 before, 2 after) to focus on immediate sentence structure while maintaining local coherence.

### 3.2 Academic Strategy (`strategies/academic.py`)
*   **Target Domain**: Scholarly Papers, Research Articles.
*   **Methodology**: **Dual-Persona Proofreading**.
    *   **Persona 1 (Literal Translator)**: Focuses on accuracy and preserving the original meaning.
    *   **Persona 2 (Academic Editor)**: Polishes the text for flow, tone, and academic rigor, "blind" to the source structure to avoid Chinglish.
*   **Key Features**:
    *   **Cross-Row Merging**: Detects split sentences and merges them. Uses placeholders `[已向上合并]` / `[已向下合并]` to maintain row alignment.
    *   **QA Check**: Post-translation check for **Critical Errors**:
        *   Omissions
        *   Misinterpretations
        *   Hallucinations
        *   *Note: Tuned to ignore stylistic changes.*
    *   **Processing**: Batch size ~15 for flow continuity.

### 3.3 Video Strategy (`strategies/video.py`)
*   **Target Domain**: Subtitles, Scripts, Transcripts.
*   **Methodology**: **Context-Aware Subtitling**.
*   **Key Features**:
    *   **Full Context Injection**: Injects the first ~3000 chars of the document to give the LLM distinct topic awareness.
    *   **Style Guide**: Automatically generates a style guide (tone, terminology) based on the input text before processing.
    *   **Transcription Audit**: Flags potential transcription errors in the source text (e.g., "pay an RMB" -> "pay an arm and a leg").
    *   **Blacklist**: Enforces a "Translationese" blacklist (e.g., avoiding "进行", "通过" as generic verbs).
    *   **VO/OS Separation**: Identifies and separates Voice-Over (VO) from On-Screen (OS) text in comments.

## 4. Configuration

All settings are managed in `config.yaml`.

### 4.1 Global Settings
*   **LLM Model**: `gemini-2.5-flash-lite` (Default for all strategies for speed/cost).
*   **API Key Config**: `GEMINI_API_KEY` (Environment variable).

### 4.2 Configurable Parameters per Strategy
| Parameter | Description | Legal | Academic | Video |
| :--- | :--- | :--- | :--- | :--- |
| `batch_size` | Rows processed per LLM call | 1 | 15 | 30 |
| `context_window` | Sliding window (rows before/after) | 3/2 | 8/0 | 5/0 |
| `inject_full_context` | Inject document start into prompt | No | No | **Yes** |
| `cross_row_merging` | Merge split sentences | No | **Yes** | No |
| `glossary_enforcement` | Level of term adherence | **Strict** | Moderate | Moderate |
| `enable_qa_check` | Post-translation validation | No | **Yes** | No |
| `enable_transcription_audit` | Check source errors | No | No | **Yes** |
| `generate_style_guide` | Pre-analysis for consistency | No | No | **Yes** |

## 5. Interface Specifications

### 5.1 CLI (`helper.py`)
Supports **Interactive Mode** (wizard) and **Quick Mode** (args).
*   **Arguments**:
    *   `-i`, `--input`: Source TSV path.
    *   `-m`, `--mode`: Strategy (`legal`, `academic`, `video`).
    *   `-o`, `--output`: Target TSV path (optional).
    *   `-g`, `--glossary`: Glossary TSV path (optional).

### 5.2 Input File Format (TSV)
Required columns:
*   `ID`: Unique identifier.
*   `Source`: Source text.
*   `Target`: Existing translation (optional, for proofreading) or empty.

### 5.3 Output File Format (TSV)
*   **Same structure** as input.
*   **Target**: Filled with translation/proofreading result.
*   **Comments** (Optional): Contains metadata, QA flags (`[[QA FLAG]]`), or audit notes (`[TRANSCRIPTION FLAG]`).

## 6. Environment & Dependencies

*   **Runtime**: Python 3.8+
*   **Dependencies**:
    *   `google-genai`: For LLM interaction.
    *   `PyYAML`: For configuration management.
    *   `python-dotenv`: For environment variable management.
    *   `tqdm`: For progress bars.

---
*Generated by Antigravity on 2025-12-13*
