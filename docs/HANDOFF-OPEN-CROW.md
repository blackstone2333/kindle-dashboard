# Kindle Dashboard → Open Crow 交接

更新时间：2026-09-05

## 当前状态

仓库：`blackstone2333/kindle-dashboard`

最近提交：

- `5d916d1`：Apple 风格周历、节气日期、黄历卡片基础；
- `73ecbd4`：周历上下滑真正切换上一周/下一周；
- `bd43439`：右侧卡片和 Agent 提示词清单。

Mac Hub 当前运行在本地 `18501` 端口，Kindle 通过 SSH 部署到 KOReader 插件目录。设备端已经验证能加载最新插件、读取日程、读取 Agent 卡片和显示节气日期。不要把 `.runtime/hub/device-token`、`.runtime/hub/agent-token`、`.runtime/hub/cards.json` 或个人日历快照提交到 Git。

## 已跑通的链路

```text
Qclaw / Agent
  PUT /api/v1/cards/<稳定ID>
  → Hub cards.json
  → GET /api/v1/snapshot
  → Kindle snapshot.json
  → Lua 卡片模型与局部刷新
```

当前 Hub 已写入一组测试卡片：`briefing`、`news`、`english`、`divination`、`quote`、`horoscope`、`question`、`task`。这些测试卡片有过期时间，只用于验收，不代表正式内容源。

卡片写入使用独立 Agent token，读取设备快照使用 device token。卡片类型和提示词见 [AGENT-CARD-PROMPTS.md](AGENT-CARD-PROMPTS.md)。

## Kindle 端交互

- 左下横滑：今日安排 → 倒计时 → 天气 → Agent 卡片；上下滑在当前卡片内翻页。
- 右上横滑：月历 ↔ Apple 风格周历；月历上下滑换月，周历上下滑换周。
- 右下横滑：后续日程 → 星座运势 → 节气/黄历；中间节气/黄历区域固定，点击显示详情。
- 设置中有“重启看板”。
- 底部 Wi-Fi 图标点击显示 Wi-Fi、Hub 日程、天气服务状态；电池百分比显示在电池图标右侧。

## 下一步验收

1. 在 Kindle 上测试右上周历：横滑切换月历/周历，上下滑切换周；确认事件落在正确日期和时间格。
2. 测试右下三个卡片，确认切换后点击不会调用错误页面。
3. 发送一张 `horoscope` 卡片，确认右下星座卡片显示；发送其他类型，确认左侧 Agent 卡片可上下翻页。
4. 测试设置中的“重启看板”，确认无需回 KOReader 主菜单即可恢复。
5. 确认 40 项 Python 测试继续通过；真机 Lua 以 KOReader 日志和 `status.json` 为最终验收依据。

## 不要改变的边界

- Kindle 只读取卡片，不执行 Agent 发送的代码或命令。
- 日历、提醒事项、天气、农历和黄历事实不由 Agent 编造；Agent 只负责内容卡片。
- 倒计时、番茄钟、随机任务打卡和电子宠物状态优先保存在 Kindle 本地。
- 不修改 KOReader 核心、KUAL 核心或 SSH 授权文件。
