# Kindle Dashboard

项目包括已定稿的 V13 横屏版式，以及 KOReader 原生真实数据版。真实版在 Kindle 本地绘制时钟、月历和时间线，由一个家庭局域网内的 Hub 提供日历、提醒事项、天气和历法数据。Agent 能力是后续可选扩展，不是核心前提。

这是一个面向已经越狱并安装 KOReader 的 Kindle 的个人/家庭项目。当前参考部署是“Mac Hub + Kindle”；未来可以替换来源适配器，但 Kindle 快照协议保持稳定。

## 公开发行版

当前代码可以作为 Mac + Kindle 的开发预览版使用。公开发布包不包含个人日程、设备令牌、局域网地址、SSH 密钥或 Apple 系统字体。

- Mac 安装说明：[docs/INSTALL-MAC.md](docs/INSTALL-MAC.md)
- Kindle USB 安装说明：[docs/INSTALL-KINDLE.md](docs/INSTALL-KINDLE.md)
- Kindle 配置模板：[device/koreader/config.example.json](device/koreader/config.example.json)
- 生成无凭据 Kindle ZIP：`python3 tools/package_kindle_release.py`

当前实施和验收状态见 [V13 真实数据版](docs/work/2026-09-05-live-v13.md)；后续独立运行、Agent 和 NAS 的路线见 [功能方案](docs/work/2026-09-05-implementation-proposal.md)。

## 真实数据版

Mac 首次导出需要允许读取日历、提醒事项。下面命令在本项目目录执行：

```sh
python3 -m pip install --target .runtime/vendor -r requirements-live.txt
python3 connectors/macos/export_snapshot.py --output .runtime/hub/apple.json
python3 tools/live_hub.py start
python3 tools/live_hub.py status
```

`tools/live_hub.py stop` 停止服务，`restart` 重启。服务脱离终端后台运行，但尚未注册 Mac 开机自启；Mac 休眠/关机时 Kindle 保留缓存，开机后需要重新启动服务。默认端口 18501。

天气位置放在 `.runtime/hub/weather-location.json`，格式如下；修改后约一分钟内生效：

```json
{"city":"YOUR_CITY","latitude":0.0,"longitude":0.0}
```

当前地理位置在服务端配置；Kindle 城市编辑界面是后续功能。时区 `Asia/Shanghai` 表示中国标准时间，不代表天气城市。

Kindle 主菜单入口为“Kindle Agent 看板 → 打开 V13 看板”。月历区域滑动切月份，点月份标题回到当月；日程区域分别滑动翻列表。点击条目查看完整内容，左下角太阳调前光，右上角齿轮提供同步状态/常显/清除残影/退出。Wi‑Fi 和电池图标只显示状态。

时钟每分钟只更新自身区域；数据没发生可见变化就不重刷。天气约30分钟取一次，变化时只更新天气区。不做定时整屏全刷；需要时通过设置手动清除残影。

设备安装和安全边界见 [设备说明](device/koreader/README.md)。NAS 和 Agent 轮播尚未部署。

## 离线演示运行

```sh
cd work/kindle-agent-dashboard
python3 render_demo.py
python3 app.py --host 127.0.0.1 --port 18500 --assets public --fixture fixtures/demo.json
```

浏览器访问 `http://127.0.0.1:18500/`，接口包括：

- `GET /health`
- `GET /manifest.json` 或 `GET /api/manifest`
- `GET /pages/today-overview.png`
- `GET /pages/agent-brief.png`

横屏 mockup 不加入竖屏 manifest，单独运行：

```sh
python3 render_landscape_demo.py
python3 render_landscape_v2_demo.py
python3 render_landscape_v3_demo.py
python3 render_landscape_v4_demo.py
python3 render_landscape_v5_demo.py
python3 render_landscape_v6_demo.py
python3 render_landscape_v7_demo.py
python3 render_landscape_v8_demo.py
python3 render_landscape_v9_demo.py
python3 render_landscape_v10_demo.py
python3 render_landscape_v11_demo.py
python3 render_landscape_v12_demo.py
```

输出 `public/pages/landscape-mockup.png`，尺寸为 `1448×1072`。它只用于横放版式评审，设备安装阶段再处理旋转和 framebuffer 方向。
V2 另存为 `public/pages/landscape-mockup-v2.png`，在右侧加入触控状态位、完整月历事件点、未来 7 天和节气/黄历示意，不覆盖 V1。
V3 另存为 `public/pages/landscape-mockup-v3.png`，顶部天气更突出，状态图标改为无边框无文字，节气/黄历移到未来 7 天之前，并保留底部留白。
V4 另存为 `public/pages/landscape-mockup-v4.png`，使用本地 vendored Lucide 图标，增加天气图标和底部状态控制区。
V5 另存为 `public/pages/landscape-mockup-v5.png`，进一步收紧顶部间距与底部控制区，去除无关说明和电量外置数字。
V6 另存为 `public/pages/landscape-mockup-v6.png`，让天气图标与时间同高度，并将天气两行文字分别对齐日期和农历；电量使用 Lucide 中电量图形表示，不显示数字。
V7 另存为 `public/pages/landscape-mockup-v7.png`，将天气块整理为地名、当前温度、天气/高低温、降雨/紫外线/风速四行右对齐信息。
V8 另存为 `public/pages/landscape-mockup-v8.png`，将天气图标与“上海 27°C”置于同一主行，并让天气范围、降雨/紫外线/风速分别与日期、农历两行对齐；底部电量仅保留图标。
V9 另存为 `public/pages/landscape-mockup-v9.png`，将城市名缩小置于温度上方，城市/大号温度与天气图标共同占据第一行；天气范围和天气指标分别与日期、农历保持字号及基线对齐。
V10 另存为 `public/pages/landscape-mockup-v10.png`，第二、三行分别严格匹配日期、农历字号与基线，压缩第一行温度下沿，并缩小下方状态图标、压缩底部留白。
V11 另存为 `public/pages/landscape-mockup-v11.png`，将温度放大到约时间高度的三分之二并上移收齐下沿，城市名改为节气字号，收紧城市与温度间距。
V12 另存为 `public/pages/landscape-mockup-v12.png`，仅放大右半部分月历、节气/黄历和下一周的日程，日程标题与左侧时间线接近同字号。
V13 已定稿，并通过独立接口提供：`GET /landscape/manifest.json`、`GET /api/landscape/manifest` 和 `GET /pages/landscape-mockup-v13.png`。字段契约见 `docs/dashboard-payload.schema.json`；manifest 包含横屏尺寸、16 级灰度、生成时间、6 小时 TTL 和 fixture 摘要，不混入竖屏 manifest。

manifest 是版本化的小型只读契约，包含设备尺寸、页序、停留秒数、SHA-256 和有效期。数据为空时使用占位卡片，长文本采用测量宽度换行并在行数上限处省略。

## Kindle 端预览

固定 V13 图片仍可由 KOReader 手动打开。`device/koreader/plugins/kindleagentdashboard.koplugin` 现在是原生真实数据插件，安装/升级 main.lua 后需重启 KOReader；不修改 KUAL 或系统组件。

## 测试

```sh
python3 -m unittest discover -s tests -v
```

## Docker 草案

`compose.demo.yml` 只绑定 `127.0.0.1:18500`，不会占用 NAS 现有 `16666`/`18423`，也没有部署到群晖。未来接入 Kindle 前，需要另行确认局域网绑定地址、鉴权、HTTPS/缓存策略、OTA 防护和设备端网络通道。

## 当前范围

- 真实版只读 Apple 日历/提醒事项和 Open-Meteo 天气，没有写回日历或待办的功能；
- Google 独立 OAuth、Agent 推送、新闻/照片轮播仍待后续实现；
- 不安装或修改 KUAL、FBInk、USBNetwork 及系统组件；
- 不修改 NAS、Docker、Tomato、AVS、Xray 或现有数据。

参考提交和采用边界见 `docs/PROJECT.md`。本项目按 MIT License 发布；第三方依赖和图标说明见 `THIRD_PARTY_NOTICES.md`。
