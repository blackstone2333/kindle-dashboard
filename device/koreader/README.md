# KOReader 原生 V13 看板

将 `plugins/kindleagentdashboard.koplugin` 安装到设备的 `/mnt/us/koreader/plugins/`。覆盖前备份现有插件，然后重启一次 KOReader。入口：“Kindle Agent 看板 → 打开 V13 看板”。

配置文件位于 `/mnt/us/koreader/settings/kindle-agent-dashboard/config.json`：

```json
{"url":"http://YOUR_HUB_LAN_IP:18501","token":"YOUR_DEVICE_TOKEN"}
```

令牌由 Hub 在本机生成，不能发布。公开发行包只提供配置模板；用户应把自己的 Hub 地址和令牌写入本地 `config.json`。插件默认使用 KOReader 的 CJK 字体，不依赖 Apple 系统字体。

## 操作

- 左下角太阳：前光调节。
- 右上角齿轮：立即同步、同步状态、常显、退出。
- 月历数字区域上/左滑到下月，下/右滑到上月；点月份标题回到当月。目前可查看以当月为中心、前后各两个月（共五个月）的已同步日程。
- 左下区域左右滑动切换“今日安排 / 倒计时 / Agent 卡片”；上下滑动仍用于当前卡片内分页。
- 右侧整块区域左右滑动切换“月历 / 周历 / 年历 / Agent 卡片”；在月历卡片中上下滑动按月翻页。
- 点击月历中的日期，右下方显示该日期的日程和待办；选中日期会显示边框，点击另一个日期即可切换。再次点击当前选中的日期，或点击右下方日期标题，可恢复“下一周的日程”。
- 点击月历中的日期只切换当天日程；在右下方点击具体日程后，可按该日程的日期和标题设置主倒计时或新增倒计时目标。倒计时保存在 Kindle 本地，不依赖 Hub。
- 左侧时间线、右下日程列表分别滑动翻页；点击条目查看全文。
- 点击黄历区域查看完整宜忌（传统民俗参考）。
- 右下角 Wi‑Fi、电池只显示设备状态。

时钟每分钟仅刷新时钟区域；数据约一分钟同步一次，但来源更新时间变化本身不会触发重绘。天气约30分钟更新，只有可见内容变化才刷新该区域。使用 KOReader `ui` 波形，不参与阅读器的累计 `partial` 闪刷升级；没有定时整屏全刷。进入、退出、唤醒及设置中的“清除残影”仍可能全刷。没有改用户的全局刷新设置。

进入看板保存原方向和常显值，退出时恢复；不改 KOReader 阅读器设置或日历/提醒事项内容。

离线保留上次有效快照；更新时间在设置的同步状态查看。Mac 停机后天气与日程不会继续更新。天气城市目前在 Mac 配置，不在设备设置中编辑。

倒计时配置保存在 `settings/kindle-agent-dashboard/countdown.json`。目标日期和标题来自所选日程；当前页面显示一个主目标和最多两个辅助目标。

## 诊断与安全

设备 settings/kindle-agent-dashboard 内有元数据 `status.json`、`request-result.json`，快照 `snapshot.json` 含私人日程。开发入口只识别固定 `open.request`、`close.request`、`refresh.request`、`screenshot.request` 文件；没有任意代码执行接口。截图保存为同目录 `screen.png`，同样包含私人信息。

当前 HTTP 仅用于可信局域网，Bearer 不会加密传输；不可直接开放公网。Kindle 用户盘经 USB 可读取，令牌与缓存需要物理保管。

个人设备旧插件备份：`/mnt/us/koreader/settings/kindle-agent-backups/2026-09-05/`。不要改 KUAL 核心或 SSH 授权文件来排查看板问题。
