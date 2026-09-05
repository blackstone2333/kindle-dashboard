# Agent 卡片接口

Hub 的日程和设备接口保持只读。Agent 通过独立的 `agent-token` 写入结构化卡片，Kindle 只读取 `/api/v1/snapshot` 中的 `cards`，不会执行卡片里的代码或命令。

启动 Hub 后，令牌保存在数据目录下的 `agent-token`（权限 600）。例如本地开发时：

```sh
AGENT_TOKEN="$(cat .runtime/hub/agent-token)"
curl -X PUT "http://127.0.0.1:18501/api/v1/cards/divination-2026-09-05" \
  -H "Authorization: Bearer ${AGENT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"type":"divination","title":"今日一签","body":"宜静心读书，娱乐内容。","symbol":"中签","generated_at":1788566400,"expires_at":1788652800}'
```

卡片字段：

- `type`：`briefing`、`news`、`english`、`divination`、`photo`、`quote`、`horoscope`、`question` 或 `task`；
- `title`、`body`：展示文字；
- `generated_at`、`expires_at`：Unix 秒，可选过期时间；
- 可附加 `symbol`、`source_url`、`priority` 等展示元数据，但不得放入可执行内容。

每日卜卦/一签建议由 Agent 每天早上生成一个带日期的稳定 ID，例如 `divination-2026-09-05`，重复提交会覆盖同一张卡片。`expires_at` 到期后 Hub 会自动从设备快照中移除。删除使用同一路径的 `DELETE` 请求。
