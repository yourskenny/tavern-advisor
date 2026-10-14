# 酒馆决策助手

Windows 本地实时酒馆战棋工作台。第一阶段复用 HearthSim 的 `hslog` 读取 Power.log，保存局面与基础建议。当前建议是可解释的启发式基线，尚不是经过高分段验证的策略或战斗模拟器。

## 开发启动

需要 Python 3.11+、Node.js 22+。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.lock.txt
npm install
.\.venv\Scripts\python scripts/sync_cards.py
npm run dev
```

访问 http://127.0.0.1:5173 。界面可切换实时与演练，导入已有 Power.log，查看快照历史。首次运行没有游戏日志时保持等待，不会将演练冒充真实对局。

## 日志连接

在连接页选择 Hearthstone 的 `Logs` 文件夹，或直接填写 `Power.log` 路径。游戏通常按启动会话创建子目录。本项目不会自动修改炉石配置；若未输出日志，退出游戏后备份并编辑 `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config`，合并以下配置后重启游戏：

```ini
[Power]
LogLevel=1
FilePrinting=true
ConsolePrinting=false
ScreenPrinting=false
Verbose=true
```

实时读取要求日志包含完整的 CREATE_GAME。身份不明、非酒馆模式、战斗阶段或金币未知时不输出购买建议。日志可能不含商店、升级费用、英雄技能费用等完整信息：这些字段显示未知，不补造数据。玩家编号可在连接页显式指定；自动识别失败时不会默认选择玩家 1。

日志超过 120 秒未更新时暂停实时建议；解析错误保持可见，修正文件后点击连接可重新读取。

导入目前保存整份日志的最后一个局面；实时监听保存每次可观察的局面变化。复盘历史的建议按当前规则重新计算，尚不保存当时建议版本。JSON 导出最多包含最近 1,000 个快照。

## 验证

```powershell
npm run check
npm run build
.\.venv\Scripts\python -m pytest
```

研究记录：[docs/research.md](docs/research.md)。架构：[docs/architecture.md](docs/architecture.md)。开发进度：[docs/progress.md](docs/progress.md)。
