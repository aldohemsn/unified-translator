# Unified Translator 开发路线图

## 本轮成果 (v1.0)

### ✅ 已实施优化
| 策略 | 优化 | 效果 |
|------|------|------|
| **Legal** | LLM 语义分段 | API 调用减少 4.5x |
| **Video** | 全文摘要压缩 | Token 减少 65% |
| **All** | 输出格式强化 | 消除分析混入翻译 |
| **Academic** | QA 敏感度调优 | 误报减少 59% |

### ✅ 已修复问题
- Legal 输出混入分析内容
- 跨行合并占位符 (`[已向上合并]`)
- 导入路径问题 (`sys.path` 修复)

---

## 未来改进方向

### P1: 生产验证反馈
> 待生产实践检验后调整

- [ ] 语义分段边界准确性调优
- [ ] 压缩摘要信息完整性验证
- [ ] 批次大小动态调整

### P2: Academic 并行 QA
```
当前: 串行 translate → qa → translate → qa
目标: 流水线 translate → (qa + translate) → ...
预期: 时间减少 30-40%
```

### P3: 可观测性
- [ ] 添加处理进度 WebSocket 推送
- [ ] 输出 Token 消耗统计
- [ ] QA Flag 聚合报告

### P4: 策略扩展
- [ ] 多语言支持 (日/韩/德)
- [ ] 自定义策略模板
- [ ] 术语库版本管理

---

## 关键设计原则

1. **质量优先**: 不牺牲翻译质量换取效率
2. **语义完整**: 批次边界由 LLM 判断，非硬规则
3. **全文语境**: 视频/字幕保留压缩语境，不截断
4. **100% QA**: 学术出版级内容全覆盖检查

---

## 文件索引

- [SPECIFICATIONS.md](file:///Users/xiaohonghe/Build/unified-translator/SPECIFICATIONS.md) - 系统规格
- [config.yaml](file:///Users/xiaohonghe/Build/unified-translator/config.yaml) - 配置参考
- [helper.py](file:///Users/xiaohonghe/Build/unified-translator/helper.py) - 交互式入口
