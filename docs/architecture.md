# 架构决策 ADR-001

状态：接受；日期：2026-10-14。

## 选择

使用 Python/FastAPI + hslog + SQLite 后端和 React/TypeScript/Vite 界面，全部只绑定本机。先提供浏览器侧边窗口；原生置顶窗口留待状态读取通过实局验证后接入。

```text
Power.log -> hslog LogParser -> EntityTreeExporter
                                  |
                             状态适配器
                                  |
                          验证后的 Snapshot
                           /             \
                 SQLite 历史         规则建议引擎
                           \             /
                              HTTP API
                                  |
                          React 中文工作台
```

## 原因

日志解析语法和枚举已有 MIT 上游实现，直接复用。SQLite 复盘保留本地；卡牌完整数据缓存并锁定 build/hash；快照独立于日志包树，后续可接 HDT 插件或许可明确的模拟器。第一阶段不要求 API 密钥。

## 数据契约

- 每个快照保存 schema_version、source、game_id、observed_at、build、phase、warnings。
- 金币、费用、玩家身份等未知量为 null。空商店不等于已知商店无可买随从。
- 演练 source=demo；导入 source=import；实时 source=live。来源状态随快照保存。
- 仅确认酒馆招募阶段时输出操作建议。血量含英雄受到伤害的扣除；护甲独立显示。
- 建议包含规则名称、证据、置信说明及结构化操作。第一阶段不输出伪造胜率。
- 实时按追加行喂给 hslog；仅新行/轮换触发状态更新。检测截断和会话目录变化；不反复重读整份文件。
- 未支持的标签和阶段需可观察，不静默将不可读日志当成正常对局。

## 非本阶段验收项

完整卡牌机制、特殊经济英雄、法术/技能决策、完整站位搜索、战斗模拟、分数收益证明、原生 overlay。接口与记录先建立，不能以占位逻辑宣称这些已完成。
