# Kindle Agent 看板结构

## 边界

项目同时保留离线演示和 KOReader 原生 V13 真实数据版。真实版只读 Mac 已授权的 Apple 日历/提醒事项及 Open-Meteo 天气；不读取 Agent 凭据，不写回日历，也未部署 NAS 服务。

## 目录与职责

```text
app.py                 # 数据降级、PW3 渲染、manifest 和只读 HTTP
render_demo.py         # 本地生成两张 PNG 的入口
render_landscape_demo.py # 单独生成横屏 mockup，不改变竖屏 manifest
fixtures/demo.json     # 固定演示输入
tests/test_app.py      # 尺寸、灰度、manifest 和 HTTP 验收
compose.demo.yml       # 独立 Docker 草案（仅 127.0.0.1:18500）
references/            # 两个上游项目的只读浅克隆，不参与运行时
device/koreader/       # 原生 V13 绘制、时钟、分页、前光和缓存客户端
connectors/macos/      # EventKit 只读日历/提醒事项导出
hub/                  # Bearer 认证快照、天气/农历/节气和原子 JSON 缓存
tools/                # 后台运行、私密配对准备、已有密钥中转运输、验收工具
.runtime/             # 忽略的真实数据、设备令牌、截图及运行依赖
```

离线演示数据流为 `fixture → prepare_data → Pillow PNG → manifest/HTTP`。

真实版数据流为 `Mac EventKit + 天气 + 农历库 → Hub JSON → Kindle client/cache → model → view`。屏幕在 Kindle 本地绘制，不依赖服务端截图。原子 JSON 适用于单设备整份只读快照，当前没有 SQLite 或 Redis 依赖。

## PW3 约束

- 逻辑画布固定 `1072×1448` 纵向；输出为 4-bit palette PNG，16 个灰度级。
- V13 原生画布为 `1448×1072`，左侧时间线、右侧月历；分钟时钟本地更新，数据约一分钟拉取一次。
- 设备通过 KOReader 原生插件绘制；不修改系统、KUAL 核心或 SSH 认证。退出恢复原方向和常显值。
- 长文本按实际字宽换行，达到上限后使用省略号；空数组转为安全占位内容。
- 45秒轮播只属于离线演示；真实版当前单页，不轮播。服务不可达时保留上次有效缓存。

## 运行与安全

Mac 服务通过 `tools/live_hub.py` 脱离终端后台运行，尚未配置开机自启。天气城市在 `.runtime/hub/weather-location.json` 配置；Kindle 城市编辑界面为后续功能。

当前 HTTP/Bearer 仅适用于可信局域网，不会加密传输，不可直接公网暴露。设备只持有看板令牌，不持有 Apple 账号或 NAS 私钥。Kindle 用户盘可经 USB 读取，令牌和缓存依赖物理保管；Mac 私密快照和截图限制文件权限。

Lucide 图标附许可证。个人真机使用本人的 Mac 字体进行 V13 校准；通用发布包不能分发 Apple 系统字体，应使用 KOReader 自带开源 Noto 字体。

当前接口合同和验收进度见 `docs/work/2026-09-05-live-v13.md`。

## 参考提交

- `ColeLundstrom/kindle-wall-dashboard` `main`: `b90ed6e77ced1ef4d272cb9c84947b6fbec1b36d`
- `jefftko/kindle-dashboard` `main`: `439a04dd2c19f03ab83fcfbb339a2712a1c1eda8`

借鉴的是服务端生成图片、缓存/鉴权边界以及 KUAL/FBInk/唤醒循环的协议思路；没有复制未审计代码到 Kindle。
