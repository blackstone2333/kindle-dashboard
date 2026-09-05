# Kindle Agent Dashboard 接管记录

## 2026-08-29：横屏天气块 V8

- 输出：`public/pages/landscape-mockup-v8.png`
- 画布：1448×1072，P 模式、4-bit、16 级纯灰度。
- 版式：天气图标与“上海 27°C”同一主行；“多云 · 22° / 30°”与日期行对齐；降雨概率、紫外线和风速与农历行对齐。
- 资产：天气、设置、亮度、Wi-Fi、电量图标来自本地 vendored Lucide 资源，来源提交 `796dad298f8d78c5da204c3e62a5ed93c2bfcd1e`，ISC License。
- 数据：仅使用 `fixtures/demo.json`，不连接真实账户、Kindle 或 NAS。
- 校验：`tests/test_landscape_v8.py` 通过；V8 SHA-256 为 `14c8908569eda5fff3a189df5889ad42a91969c3130d1453b3464aecb96541c7`。

旧版 V1–V7 预览保留不变，设备安装和 NAS 部署仍需单独确认。

## 2026-08-29：横屏天气块 V9

- 输出：`public/pages/landscape-mockup-v9.png`，保留 V8 不覆盖。
- 第一行：Lucide 天气图标与城市/温度信息同一高度带，城市名小号置上、温度大号置下。
- 第二行：天气状况与高低温使用日期行字号和基线；第三行：降雨概率、紫外线、风速使用农历行字号和基线。
- 校验：`tests/test_landscape_v9.py` 通过；1448×1072、P 模式、4-bit、16 级纯灰度；SHA-256 `bb19c7665530de47caa33f875a748dc83e5251f0df2bf130730f78baa643daee`。

## 2026-08-29：横屏天气块 V10

- 输出：`public/pages/landscape-mockup-v10.png`，保留 V9 不覆盖。
- 第二行严格使用日期行字号（30px），第三行严格使用农历行字号（23px）；第一行温度缩小并收进图标/时间的下沿范围。
- 底部亮度、Wi-Fi、电量图标缩小并下移，底部留白压缩。
- 校验：`tests/test_landscape_v10.py` 通过；1448×1072、P 模式、4-bit、16 级纯灰度；SHA-256 `ce74ed36356d451412b81a9d0efdedbbc803a15e01f6510ab450029ec15b0b9e`。

## 2026-08-29：横屏天气块 V11

- 输出：`public/pages/landscape-mockup-v11.png`，保留 V10 不覆盖。
- 温度约为时间高度的三分之二并上移，确保下沿不超过图标；城市名使用节气字号并收紧间距；第二、三行继续严格匹配日期/农历字号与基线。
- 校验：`tests/test_landscape_v11.py` 通过；1448×1072、P 模式、4-bit、16 级纯灰度；SHA-256 `3fe6be661169b0fcd7f98a54b6a1b9e83c29c0b5ce0921ec619ff0afae7ea28a`。

## 2026-08-29：右栏可读性 V12

- 输出：`public/pages/landscape-mockup-v12.png`，左侧天气与时间区域保持 V11 不变。
- 放大月历星期/日期、节气、黄历和“下一周的日程”；日程日期、时间、标题、类型利用原有空隙并提高到接近左侧时间线字号。
- 校验：`tests/test_landscape_v12.py` 通过；1448×1072、P 模式、4-bit、16 级纯灰度。

## V13 定稿后的本地接口

V13 通过 `/landscape/manifest.json` 或 `/api/landscape/manifest` 提供只读 manifest，图片从 `/pages/landscape-mockup-v13.png` 读取。字段契约位于 `docs/dashboard-payload.schema.json`，当前仅使用 fixture，不连接 Kindle、NAS 或真实账号。

## 2026-08-29：KUAL 看板动作连续失败（待区分设备环境）

### 现象

- KUAL 可以显示“Kindle Agent 看板”及其子项。
- 点击“打开 V13 横屏预览”后回到 Kindle 桌面，未进入 KOReader。
- 设备端没有生成 `documents/kindle-agent-dashboard-kual.log`；`koreader/crash.log` 没有对应的新启动记录。

### 已验证与排除

- 看板目录包含 `config.xml`、`menu.json`，以及可读可执行的启动脚本。
- 已尝试直接调用 `/mnt/us/koreader/koreader.sh`、扩展内包装脚本、显式 `/bin/sh`、根目录 `./open-preview.sh` 和标准 `./bin/open-preview.sh`；五种写法均未产生启动标记。
- V13 图片此前由 KOReader 正常打开过，因此图片格式和 KOReader 图像渲染不是当前证据指向的原因。

### 当前判断

失败点位于 KUAL 对动作的调度/执行层，具体是路径解析、权限/执行策略或 KUAL 进程缓存之一；在没有 Kindle 端 shell 的情况下，继续排列组合菜单字段没有区分度。

### 不再重复

不再重复上述五种动作路径或仅改变 `params` 的等价写法。

### 唯一下一步区分性测试

用户点击设备原有的 `KUAL → KOReader → Start KOReader`：

1. 若原有入口能启动，KUAL 调度正常；下一步复用该已验证启动链打开 V13。
2. 若原有入口也回桌面，问题属于设备/KUAL/KOReader 环境，先停止看板扩展改动。

### 区分性测试结果

用户确认设备原有 `KUAL → KOReader → Start KOReader` 能正常打开 KOReader。由此排除 KUAL/KOReader 的整体启动故障，问题收敛为自定义扩展动作的调度上下文或路径解析。

### 当前处理

不再继续排列自定义扩展的动作写法；改在已验证可用的 KOReader 扩展菜单中增加 V13 文件参数，复用同一 `/mnt/us/koreader/koreader.sh --kual` 启动链。自定义扩展目录保留作记录，不作为当前启动入口。

设备端已完成该菜单补丁：`/mnt/us/extensions/koreader/menu.json` 新增“打开 Kindle Agent V13”，动作与原有“Start KOReader”一致，仅增加 `/mnt/us/documents/kindle-agent-dashboard-v13.png` 文件参数；JSON 校验通过。等待用户运行验收。

### 参数传递证据

用户实测后，`koreader/crash.log` 新增 22:56:04 的 KOReader 启动记录，但没有 `opening file` 行，随后在 22:56:50 正常退出。由此确认 KUAL 的 `params` 在此环境下没有按空格拆成 `--kual` 与文件路径两个参数；KOReader 启动成功但忽略了文件参数。

### 修复决定

停止在菜单中传递带空格的 `params`。改为在现有 KOReader 扩展的 `bin/` 目录增加无参数脚本，脚本内部固定调用 `/bin/sh /mnt/us/koreader/koreader.sh --kual /mnt/us/documents/kindle-agent-dashboard-v13.png`；菜单项只调用该脚本。

该修复已写入设备：`/mnt/us/extensions/koreader/bin/kindle-agent-dashboard-v13.sh`，并将 KOReader 菜单项改为 `./bin/kindle-agent-dashboard-v13.sh`（无 `params`）。脚本和菜单均完成语法/JSON 校验，等待用户实测。

### 后续复测结果

用户再次反馈“没反应”；回读设备后，`koreader/crash.log` 没有 22:56:50 后的新启动记录，因此无法证明新增菜单项已被 KUAL 加载或执行。自动入口暂停，不再继续排列菜单动作。

### 当前安全验证路径

使用已确认可工作的 `KUAL → KOReader → Start KOReader`，在 KOReader 文件管理器中手动打开 `/mnt/us/documents/kindle-agent-dashboard-v13.png`。该步骤只验证 V13 在 Kindle 屏幕上的最终显示，不涉及新的启动链。

用户已确认手动打开正常。随后新增 KOReader 插件 `/mnt/us/koreader/plugins/kindleagentdashboard.koplugin/main.lua`，在 KOReader 主菜单注册“Kindle Agent 看板 → 打开 V13 横屏预览”，回调直接执行 `ReaderUI:showReader("/mnt/us/documents/kindle-agent-dashboard-v13.png")`。插件已复制到设备且与本地校验一致，等待 KOReader 重启后的首次加载验收。

## 2026-08-29：手动验收路径确认

- 用户确认采用手动验收方式；当前不再尝试 KUAL 自定义动作或参数变体。
- 唯一待测步骤：断开 USB，完全退出并重新启动 KOReader，在主菜单打开“Kindle Agent 看板 → 打开 V13 横屏预览”。
- 通过条件：菜单项可见，点击后进入 `/mnt/us/documents/kindle-agent-dashboard-v13.png`，且 KOReader 不闪退。
- 失败处理：重新插 USB 后读取 `koreader/crash.log` 最新尾部；不凭猜测继续修改 KUAL。

## 2026-08-29：KOReader 插件手动验收再次失败

- 用户在完全重启 KOReader 后仍反馈“不行”。这条反馈没有说明是菜单不可见、点击无反应还是闪退，因此根因暂未知。
- 当前唯一区分性动作：重新连接 USB，读取 `koreader/crash.log` 最新尾部；不再尝试 KUAL 动作或插件代码排列组合。

## 2026-08-29：用户主动暂停

- 用户决定暂不继续 Kindle 端安装与排查。
- 保留现有 V13 图片、KOReader 插件和失败证据；不删除设备文件，不再执行新的安装或诊断动作。
- 若恢复，第一步仍是读取 `koreader/crash.log`，以区分插件加载、菜单注册和文件打开问题。

## 2026-09-05：规划复核，设备实施仍暂停

- 新的 [V13 功能实现方案](../work/2026-09-05-implementation-proposal.md) 已形成；本轮只检查本地源码和历史证据，没有连接或操作设备。
- 现有插件只有注册菜单和打开 PNG 的回调，不具有动态看板能力。后续最小组件验收应覆盖显示、退出、亮度、休眠/USB 恢复，而非仅菜单可见。
- 修正历史证据强度：22:56 的启动记录没有 `opening file`，只能说明该次没有记录成功打开目标文件；不足以单独证明 KUAL 如何拆分 `params`。“不行”也不能确认用户是否完成完整重启或失败发生在哪个环节。当前根因仍未知。
