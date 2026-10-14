# 上游调研与复用记录

调研日期：2026-10-14。来自 GitHub API、上游 README、PyPI 和 npm registry 的实际查询。最近提交仅表明维护活动，不代表当前酒馆机制已经全部支持。

| 项目 | 证据与维护情况 | 采用决定 |
| --- | --- | --- |
| [Hearthstone Deck Tracker](https://github.com/HearthSim/Hearthstone-Deck-Tracker) | Windows C# 记牌器；仓库最近推送 2026-10-14；根目录未提供单一 SPDX 许可，存在 licenses 目录 | 参考日志与状态分层架构；不复制源代码，不假定 Bob's Buddy 可自由复用 |
| [python-hslog](https://github.com/HearthSim/python-hslog) | MIT；最近推送 2026-08-15；PyPI 1.20.0；支持 Power.log 包树和实体树导出、友方识别 | 直接依赖，避免自己重写日志语法解析器 |
| [python-hearthstone](https://github.com/HearthSim/python-hearthstone) | MIT；最近推送 2026-10-13；提供 GameTag、Zone 等枚举和实体模型 | 直接依赖；用枚举解释标签，不硬编码不明数字 |
| [HearthstoneJSON client](https://github.com/HearthSim/hearthstonejson-client) / [数据服务](https://hearthstonejson.com/) | 社区卡牌数据服务；客户端最近推送 2026-08-13；支持中文卡牌字段 | 从数据 API 缓存中文卡牌，记录 build 和 SHA-256；数据与图片权利不等同于客户端许可 |
| [Firestone](https://github.com/Zero-to-Heroes/firestone) | Angular/Nx + Overwolf/Electron；最近推送 2026-10-11；依赖 @firestone-hs/simulate-bgs-battle | 参考模块边界；不搬整套 Overwolf 依赖 |
| [Firestone 模拟包](https://www.npmjs.com/package/@firestone-hs/simulate-bgs-battle) | npm 最新 1.1.772；license 为 All rights reserved；主程序使用版本范围 ^1.1.682 | 不安装、不调用。保留模拟接口，许可明确后再选引擎 |
| [twanvl 模拟器](https://github.com/twanvl/hearthstone-battlegrounds-simulator) | 搜索返回最后推送 2020-01-22 | 当前版本适配证据不足，不作为战斗胜率来源 |
| [battlegrounds-rs](https://github.com/utilForever/battlegrounds-rs) | 搜索返回最后推送 2022-09-25 | 不作为当前版本引擎 |
| [Ghastcoiler](https://github.com/janvdvegt/Ghastcoiler) / [HSBRSIM](https://github.com/Gallo13th/HSBRSIM) | 搜索返回较新推送；尚未完成机制覆盖和许可审计 | 留在候选列表；不能仅凭更新时间接入 |

## 数据来源纠正

最初对话提到的 `HearthSim/hearthstonejson` 仓库实际返回 404。真实客户端仓库为 `HearthSim/hearthstonejson-client`，数据入口为 `https://api.hearthstonejson.com/v1/`。不继续沿用错误链接。

## 验证限制

- 当前机器常见安装路径和卸载注册表中未发现 Hearthstone。因此本阶段可验证上游解析器、合成日志、历史导入和 UI；真实客户端映射仍需实局样本。
- 不能用通用随从身材估算冒充战斗胜率。第一阶段仅输出明确标注的基础经济建议。
- Power.log 中能看到的实体不都属于当前商店。只在已确认招募阶段、已识别友方、对方确认为酒馆老板时构建商店；否则留空。
- 最新完整卡牌表不等于当前启用卡池。没有补丁卡池清单前，不宣称掌握完整当前轮换。
