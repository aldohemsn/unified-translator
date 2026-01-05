# 🔧 Utility Scripts

本目录包含 Unified Translator 的辅助工具脚本。

## 目录结构

```
scripts/
├── docx/                    # DOCX 文档处理工具
├── qa/                      # 质量检查工具
├── apply_client_format.py   # 应用客户格式规范
├── generate_review_prompt.py # 生成外部审校 Prompt
├── convert_for_video.py     # 转换 TSV 格式为视频策略格式
├── analyze_tsv.py           # TSV 文件统计分析
├── verify_segmentation.py   # 验证分段逻辑
└── debug_auth.py            # API 认证调试
```

---

## DOCX 处理工具 (`docx/`)

| 脚本 | 用途 | 示例 |
|------|------|------|
| `extract_docx_to_tsv.py` | 从 DOCX 表格提取双语内容到 TSV | `python scripts/docx/extract_docx_to_tsv.py input.docx output.tsv` |
| `extract_glossary_table.py` | 提取术语表 | `python scripts/docx/extract_glossary_table.py glossary.docx terms.tsv` |
| `extract_all_glossaries.py` | 从多表格文档提取所有术语 | `python scripts/docx/extract_all_glossaries.py doc.docx all_terms.tsv` |
| `tsv_to_docx.py` | 将校对后的 TSV 转回 DOCX | `python scripts/docx/tsv_to_docx.py proofread.tsv output.docx` |
| `compare_docx.py` | 比较两个 DOCX 文件的表格差异 | 直接编辑脚本中的文件路径后运行 |
| `inspect_docx.py` | 检查 DOCX 结构 | `python scripts/docx/inspect_docx.py document.docx` |

---

## 质量检查工具 (`qa/`)

| 脚本 | 用途 | 示例 |
|------|------|------|
| `check_compliance.py` | 检查译文是否符合客户规范（标点、长度等） | `python scripts/qa/check_compliance.py output.tsv` |
| `check_locked.py` | 检查锁定行状态 | 修改脚本中的 `file_path` 后运行 |
| `check_length_snippet.py` | 检查字幕长度限制 | 修改脚本中的文本后运行 |

---

## 其他工具

| 脚本 | 用途 |
|------|------|
| `apply_client_format.py` | 应用严格的客户格式规则（标点转换、引号规范等） |
| `generate_review_prompt.py` | 基于 CIL 上下文生成外部 LLM 审校指令 |
| `convert_for_video.py` | 将 `ID,EN,ZH` 格式转换为 `ID,Source,Target` |
| `analyze_tsv.py` | 分析 TSV 文件的行数、字符统计 |
| `verify_segmentation.py` | 验证智能分段合并逻辑 |

---

## 使用说明

从项目根目录运行脚本：

```bash
# 从项目根目录
python scripts/docx/extract_docx_to_tsv.py input.docx output.tsv
python scripts/qa/check_compliance.py translated.tsv
```

---

*最后更新: 2026-01-05*
