# Video Translation Service - Logic Breakdown

## 📋 Executive Summary

The **Video Strategy** in the Unified Translator framework is specifically designed for translating **subtitles, scripts, and video transcripts**. It addresses unique challenges in video translation:

- **Fragmented context** (dialogues jump between speakers/scenes)
- **Transcription errors** (ASR mistakes, homophones)
- **Translation artifacts** ("Translationese" - awkward literal translations)
- **VO vs. OS text** (Voice-Over needs fluidity, On-Screen needs conciseness)

---

## 🏗️ Architecture Overview

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Video Translation Pipeline                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. INPUT: TSV file (ID, Source, Target)                        │
│     ↓                                                            │
│  2. SETUP PHASE:                                                 │
│     ├─→ Compress Full Transcript → Scene Summary (500 chars)    │
│     └─→ Generate Style Guide → VO/OS Guidelines                 │
│     ↓                                                            │
│  3. BATCH PROCESSING:                                            │
│     ├─→ Build Context Window (History + Scene Summary)          │
│     ├─→ Apply Blacklist (Translationese Prevention)             │
│     ├─→ Transcription Audit (Flag ASR errors)                   │
│     ├─→ Translation/Proofreading (LLM Call)                      │
│     └─→ VO/OS Separation (Comments Field)                       │
│     ↓                                                            │
│  4. OUTPUT: Enhanced TSV (ID, Source, Target, Comments)          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Core Components Deep Dive

### 1. **Setup Phase** (`setup()` method)

The setup phase runs **once before processing** to prepare contextual aids:

#### A. Compressed Context Generation

**Problem:** Full transcripts can be 10,000+ characters, consuming excessive tokens.

**Solution:** Compress the first 500 lines (5000 chars) into a structured 500-character summary.

**Implementation:**
```python
def _generate_compressed_context(self, full_text: str):
    compress_prompt = f"""为以下视频字幕生成【场景摘要】，用于指导翻译。

    请包含：
    1. **主题**: 视频在讲什么（一句话）
    2. **说话人**: 有哪些角色/身份（如：主持人、嘉宾A、旁白）
    3. **语境**: 正式/口语，新闻/教程/剧情/采访
    4. **关键术语**: 专有名词、人名、品牌名（列出 5-10 个）
    5. **特殊注意**: 任何翻译时需要注意的点

    字幕原文（前 5000 字符）：
    {full_text[:5000]}
    """
    
    response = llm.generate(compress_prompt, model='gemini-2.5-flash-lite')
    self.transcript_context = response.strip()  # Stored for batch processing
```

**Example Output:**
```
主题：科技产品发布会
说话人：主持人、CEO、技术演示者
语境：正式发布会，偶有轻松互动
关键术语：AI芯片、神经引擎、ProMotion、MagSafe、iOS 18
特殊注意：保持品牌名英文，技术术语需专业对应
```

**Token Savings:** ~84% reduction (5000 → 500 chars)

#### B. Style Guide Generation

**Purpose:** Establish translation conventions **before** processing begins.

**Implementation:**
```python
def _generate_detailed_style_guide(self, llm, text):
    prompt = f"""
    You are a Senior Localization Architect for Video Content.
    Task: Create a "Best Efficient Style Guide".
    
    Sections Required:
    1. **Project Context**: Topic, Vibe (e.g., Casual YouTube vs. Formal Doc).
    2. **Stylistic Protocols**:
       - **Voice-Over (VO)**: Guidelines for spoken narrative (fluidity, breath).
       - **On-Screen Text (OS)**: Guidelines for titles/labels (conciseness, nominal style).
    3. **Formatting**: Rules for numbers, punctuation in subtitles.
    
    Source Text Snippet: {text[:5000]}
    """
    
    self.style_guide = llm.generate(prompt, model='gemini-2.5-flash')
```

**Example Output:**
```
**Project Context:**
- Topic: Tech product launch event
- Vibe: Professional yet engaging, mix of scripted and spontaneous

**Stylistic Protocols:**
- VO: Natural flow, complete sentences, allow reordering for Chinese grammar
- OS: Terse, keyword-focused, preserve alignment with visuals

**Formatting:**
- Numbers: Use Arabic numerals for specs (8GB), Chinese for narrative (八个)
- Punctuation: Minimize in OS, natural in VO
```

---

### 2. **Batch Processing Loop** (`process_batch()` method)

This is the **main translation engine**, called repeatedly by the Processor for each batch of rows.

#### Configuration
```yaml
# From config.yaml
video:
  batch_size: 30            # Large batches (video has high context continuity)
  context_window:
    before: 5               # Include 5 previous rows for context
    after: 0                # No lookahead needed
  inject_full_context: true # Use compressed scene summary
```

#### Processing Steps

**Step 1: Format Batch Data**
```python
formatted_batch = []
for r in batch_rows:
    formatted_batch.append({
        'ID': r.get('ID'),
        'English': r.get('Source'),
        'Chinese': r.get('Target', '')  # Empty if translation mode
    })
```

**Step 2: Build History Context**
```python
# Get last 5 processed rows for sliding window
history_snippet = json.dumps([
    {'English': r['Source'], 'Chinese': r['Target']}
    for r in history_rows[-5:]
], ensure_ascii=False)
```

**Step 3: Construct Translationese Blacklist**
```python
blacklist_terms = ['进行', '通过', '旨在', '它', '任何']  # From config

blacklist_instruction = """
**NEGATIVE CONSTRAINTS (Translationese Blacklist)**:
- Do NOT use "进行" (avoid "进行讨论", use "讨论")
- Do NOT use "通过" (avoid "通过...方式")
- Do NOT use "旨在" (overly formal)
- Do NOT use "它" (Chinese often omits pronouns)
- Do NOT use "任何" (use specific terms)
"""
```

**Step 4: Build Comprehensive Prompt**
```python
prompt = f"""
[STYLE GUIDE]
{self.style_guide}  # Generated in setup

{blacklist_instruction}

[SCENE SUMMARY (Compressed Context)]
{self.transcript_context}  # Generated in setup

[PREVIOUS CONTEXT]
{history_snippet}  # Last 5 rows

[TASK]
1. **Transcription Audit**: Check 'English' source for typos, ASR errors (homophones), or wrong names.
   - Protocol: If error found, PREPEND "⚠️ [TRANSCRIPTION FLAG]: <Note>" to 'Comments'.
2. **Translation/Proofreading**:
   - If 'Chinese' is empty: Translate the English source.
   - If 'Chinese' exists: Proofread and improve the existing translation.
   - Determine if segment is VO (Spoken) or OS (Text).
   - Apply appropriate style (VO=Fluid, OS=Concise).

[INPUT DATA]
{json.dumps(formatted_batch, indent=2, ensure_ascii=False)}

[OUTPUT FORMAT]
JSON Array of {{ "ID": "...", "Chinese_Proofread": "...", "Comments": "..." }}
"""
```

**Step 5: LLM Call**
```python
response = llm_client.generate(
    prompt,
    model='gemini-2.5-pro',  # High-quality model for translation
    response_mime_type='application/json'
)
results = json.loads(response)
```

**Step 6: Process Results**
```python
for row in batch_rows:
    res = result_map.get(row['ID'], {})
    
    output.append({
        'ID': row['ID'],
        'Source': row['Source'],
        'Target': res.get('Chinese_Proofread', row.get('Target', '')),
        'Comments': res.get('Comments', '')  # Contains flags, VO/OS tags
    })
```

---

## 🎯 Key Features Explained

### Feature 1: **Transcription Audit**

**Why:** ASR (Automatic Speech Recognition) often produces homophones or mishears names.

**Example:**
- **Source (ASR Output):** "pay an RMB"
- **Actual Speech:** "pay an arm and a leg"

**Detection Logic:**
```python
# LLM is instructed to flag suspicious transcriptions:
"""
1. **Transcription Audit**: Check 'English' source for typos, ASR errors (homophones), or wrong names.
   - Protocol: If error found, PREPEND "⚠️ [TRANSCRIPTION FLAG]: <Note>" to 'Comments'.
"""
```

**Output:**
```json
{
  "ID": "42",
  "Chinese_Proofread": "付出巨大代价",
  "Comments": "⚠️ [TRANSCRIPTION FLAG]: Suspected 'pay an RMB' should be 'pay an arm and a leg'"
}
```

---

### Feature 2: **Translationese Blacklist**

**Problem:** Direct translation often produces awkward Chinese (翻译腔 - "Translationese").

**Bad Example:**
- EN: "Through discussion, we achieve progress"
- BAD CN: "通过讨论，我们进行进步" (literally "through discussion, we perform progress")
- GOOD CN: "讨论后，我们取得进展" ("after discussion, we achieve progress")

**Implementation:**
```yaml
# config.yaml
blacklist_terms:
  - "进行"  # Generic verb ("perform/carry out")
  - "通过"  # "Through" (overused preposition)
  - "旨在"  # "Aims to" (overly formal)
  - "它"    # "It" (Chinese omits pronouns naturally)
  - "任何"  # "Any" (prefer specific terms)
```

**LLM Instruction:**
```
**NEGATIVE CONSTRAINTS (Translationese Blacklist)**:
- Do NOT use "进行" (avoid "进行讨论", use "讨论")
- Do NOT use "通过" (avoid "通过...方式")
...
```

---

### Feature 3: **VO/OS Separation**

**Concept:**
- **VO (Voice-Over):** Spoken dialogue/narration → needs natural flow
- **OS (On-Screen):** Titles, labels, UI text → needs conciseness

**Translation Approach:**

| Type | English | VO Translation | OS Translation |
|------|---------|---------------|----------------|
| VO | "Welcome to our comprehensive product showcase" | "欢迎来到我们的产品展示会" (natural) | ❌ (too long for subtitle) |
| OS | "Click here to learn more" | ❌ (not spoken) | "点击了解详情" (terse) |

**Detection:**
```python
# LLM is instructed to:
"""
2. **Translation/Proofreading**:
   - Determine if segment is VO (Spoken) or OS (Text).
   - Apply appropriate style (VO=Fluid, OS=Concise).
"""
```

**Output:**
```json
{
  "ID": "10",
  "Chinese_Proofread": "点击了解详情",
  "Comments": "OS (On-Screen Text) - kept concise for visual alignment"
}
```

---

### Feature 4: **Context Compression**

**Problem:** Video transcripts are long, but injecting full text wastes tokens.

**Before (Naive Approach):**
```python
# Inject first 3000 characters raw
prompt = f"""
[FULL TRANSCRIPT]
{' '.join(all_rows[:500])}  # ~3000 chars

[CURRENT BATCH]
{current_batch}
"""
```
- **Token Cost:** ~750 tokens per batch
- **Context Quality:** Lots of noise (repetition, filler words)

**After (Compressed Approach):**
```python
# Compress to structured 500-char summary
prompt = f"""
[SCENE SUMMARY]
主题：科技产品发布会
说话人：主持人、CEO
关键术语：AI芯片、ProMotion
"""
```
- **Token Cost:** ~125 tokens per batch (84% reduction)
- **Context Quality:** High (curated, structured)

---

## 🛠️ Model Selection Strategy

The Video Strategy uses **different models for different stages** to optimize cost/quality:

```yaml
models:
  context_compression: "gemini-2.5-flash-lite"  # Fast compression
  style_guide: "gemini-2.5-flash"              # Medium quality
  translation: "gemini-2.5-pro"                # High quality ⭐
```

**Rationale:**
- **Setup (1x):** Use cheaper models (flash-lite/flash) since it runs once
- **Translation (Nx):** Use premium model (pro) since it runs for every batch

**Cost Example (1000-row file):**
- Setup: 2 calls × flash = $0.002
- Translation: 34 batches × pro = $0.17
- **Total:** ~$0.172 (vs. $0.50 if all-pro)

---

## 🎓 Translation Philosophy

The Video Strategy embodies the **"Full Context Constraint Model" (全语境约束模式)**:

### Core Principles

1. **Strong Contextual Anchoring**
   - Inject scene summary into every batch
   - Maintain sliding window of 5 previous rows
   - Prevents jarring context shifts

2. **Negative Constraints**
   - Blacklist beats positive rules (easier to enforce)
   - Example: "Don't use 进行" vs. "Use natural verbs" (latter is vague)

3. **Dual Quality Gates**
   - **Transcription Audit:** Ensures source quality
   - **Translationese Blacklist:** Ensures target fluidity

4. **Adaptive Styling**
   - VO vs. OS requires different translation strategies
   - Style guide captures project-specific nuances

---

## 📊 Configuration Reference

### Processing Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `batch_size` | 30 | Large batches work because video has high topic continuity |
| `context_window.before` | 5 | Enough for dialogue context without excessive tokens |
| `context_window.after` | 0 | No need to look ahead (not merging cross-row) |
| `inject_full_context` | true | Critical for video - prevents topic drift |
| `full_context_max_chars` | 3000 | First ~500 rows (compressed to 500 chars) |

### Feature Flags

| Feature | Enabled | Purpose |
|---------|---------|---------|
| `generate_style_guide` | ✅ | Pre-analysis for VO/OS conventions |
| `enable_transcription_audit` | ✅ | Flag ASR errors |
| `enable_blacklist` | ✅ | Prevent Translationese |
| `cross_row_merging` | ❌ | Subtitles must maintain timing alignment |
| `enable_qa_check` | ❌ | Transcription audit is sufficient |

---

## 🔄 End-to-End Example

### Input TSV
```tsv
ID	Source	Target
1	Welcome to the show!	
2	Today we're talking about AI.	
3	pay an RMB	
```

### Processing

**Row 1:**
- Style: VO (spoken)
- Blacklist: ❌ (no violations)
- Transcription: ✅ (clean)
- Output: `欢迎来到节目！`

**Row 2:**
- Style: VO (spoken)
- Context: "Welcome to the show!" (previous row)
- Output: `今天我们聊聊人工智能。`

**Row 3:**
- Transcription: ⚠️ Suspicious ("pay an RMB" likely "pay an arm and a leg")
- Output: `付出巨大代价` (corrected translation)
- Comment: `⚠️ [TRANSCRIPTION FLAG]: Suspected ASR error`

### Output TSV
```tsv
ID	Source	Target	Comments
1	Welcome to the show!	欢迎来到节目！	VO
2	Today we're talking about AI.	今天我们聊聊人工智能。	VO
3	pay an RMB	付出巨大代价	⚠️ [TRANSCRIPTION FLAG]: Suspected ASR error - likely "pay an arm and a leg"
```

---

## 🚀 Usage

### CLI
```bash
# Translation mode (empty Target column)
python helper.py -i subtitles.tsv -m video

# Proofreading mode (existing Target translations)
python helper.py -i subtitles.tsv -m video
```

### Programmatic
```python
from strategies.video import VideoStrategy
from core.llm_client import LLMClient
from core.processor import Processor

config = load_yaml('config.yaml')
strategy = VideoStrategy(config)
strategy.setup('input.tsv')  # Generate scene summary + style guide

processor = Processor(config, LLMClient(config))
processor.run('input.tsv', 'output.tsv', strategy)
```

---

## 📝 Key Takeaways

1. **Context is King**: Compressed scene summary provides global awareness
2. **Blacklists > Rules**: Negative constraints are easier to enforce than positive guidelines
3. **Multi-Stage Models**: Use cheap models for setup, premium for translation
4. **Quality Gates**: Transcription audit + translationese prevention = high-quality output
5. **Adaptive Styling**: VO vs. OS requires different translation philosophies

---

## 🔗 Related Files

- **Implementation:** `strategies/video.py`
- **Configuration:** `config.yaml` (lines 110-154)
- **Base Logic:** `strategies/base_strategy.py`
- **Processing Loop:** `core/processor.py`
- **Methodology:** `METHODOLOGY.md` (Section 3)

---

*Last Updated: 2026-01-04*  
*Author: Code Analysis by Antigravity*
