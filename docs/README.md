# 📚 Unified Translator Documentation

本目录包含 Unified Translator 项目的所有技术文档。

## 核心文档

| 文档 | 描述 |
|------|------|
| [SPECIFICATIONS.md](./SPECIFICATIONS.md) | 系统规格说明书，包含架构、数据流、策略配置 |
| [METHODOLOGY.md](./METHODOLOGY.md) | 翻译方法论白皮书，CIL/双角色/全语境三大核心理论 |
| [ROADMAP.md](./ROADMAP.md) | 开发路线图，已完成优化与未来改进方向 |

## 策略详解

| 文档 | 对应策略 | 描述 |
|------|----------|------|
| [ACADEMIC_STRATEGY_EXPLAINED.md](./ACADEMIC_STRATEGY_EXPLAINED.md) | `academic.py` | 学术翻译助手：双重人设、术语提取、语义分块、QA检查 |
| [VIDEO_TRANSLATION_LOGIC_EXPLAINED.md](./VIDEO_TRANSLATION_LOGIC_EXPLAINED.md) | `video.py` | 视频字幕翻译：场景压缩、风格指南、转录审核、翻译腔黑名单 |

## 成本分析

| 文档 | 描述 |
|------|------|
| [MODEL_TOKEN_ANALYSIS.md](./MODEL_TOKEN_ANALYSIS.md) | 各策略的模型分配与 Token 成本分析 |

---

## 开发日志

阶段性开发总结报告已归档至 `logs/` 目录：
- `SUMMARY_20251217.md` - 法律翻译策略优化
- `SUMMARY_PHASE2_20251217.md` - 锁定行机制实现
- `SUMMARY_PHASE2_20251218.md` - 智能分段与风格控制

---

*最后更新: 2026-01-05*
