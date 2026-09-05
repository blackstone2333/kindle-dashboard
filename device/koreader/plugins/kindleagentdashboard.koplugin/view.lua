local Device = require("device")
local UIManager = require("ui/uimanager")
local InputContainer = require("ui/widget/container/inputcontainer")
local TextWidget = require("ui/widget/textwidget")
local ImageWidget = require("ui/widget/imagewidget")
local Font = require("ui/font")
local Geom = require("ui/geometry")
local Blitbuffer = require("ffi/blitbuffer")
local NetworkMgr = require("ui/network/manager")
local logger = require("logger")
local Screen = Device.screen
local View = InputContainer:extend{ name = "KindleAgentDashboardView", covers_fullscreen = true }

local function str(value, fallback)
    if type(value) == "string" or type(value) == "number" then return tostring(value) end
    return fallback or "--"
end
local function number(value, suffix)
    return type(value) == "number" and tostring(math.floor(value + 0.5)) .. (suffix or "") or "--"
end
local function gray(value) return Blitbuffer.Color8(math.floor(value / 17 + 0.5) * 17) end
local function meta(item)
    local m = type(item.meta) == "table" and item.meta or {}
    local parts = {}
    for _, key in ipairs(item.kind == "待办" and {"list"} or {"calendar", "location"}) do
        if type(m[key]) == "string" and m[key] ~= "" then parts[#parts+1] = m[key] end
    end
    return table.concat(parts, " · ")
end
local function summary(value)
    if type(value) == "table" then return table.concat(value, " · ") end
    return str(value, "暂无")
end
local function short_summary(value)
    if type(value) ~= "table" then return summary(value) end
    return table.concat(value, " · ", 1, math.min(2, #value))
end

local function countdown_days(item)
    if not item then return "--" end
    if item.state == "today" then return "今天" end
    if item.state == "past" then return "已过 " .. tostring(math.abs(item.days)) .. " 天" end
    return tostring(item.days) .. " 天"
end

local function countdown_secondary_label(item)
    return str(item and item.title, "目标日") .. " " .. countdown_days(item)
end

function View:init()
    self.cache = dofile(self.plugin_path .. "/cache.lua")
    self.model = dofile(self.plugin_path .. "/model.lua")
    self.updates = dofile(self.plugin_path .. "/updates.lua")
    self.client = dofile(self.plugin_path .. "/client.lua").new(self.root, self.plugin_path)
    self.snapshot = self.cache.read(self.root .. "/snapshot.json") or {
        schema_version = 1, generated_at = 0, utc_offset = 28800, events = {}, tasks = {}, days = {}, sources = {},
    }
    self.page, self.future_page, self.render_count = 0, 0, 0
    self.countdown_path = self.root .. "/countdown.json"
    self.countdown_config = self.cache.read(self.countdown_path) or {version=1,primary_id="primary",targets={}}
    self.month_offset, self.refresh_batches, self.full_refreshes = 0, 0, 1
    self.last_request, self.last_device_poll = 0, os.time()
    self.last_refresh = {at=os.time(),mode="full",regions={"initial"}}
    self.icons = {}
    self.dimen = Geom:new{ x = 0, y = 0, w = Screen:getWidth(), h = Screen:getHeight() }
    self.scale = math.min(self.dimen.w / 1448, self.dimen.h / 1072)
    self.font_scale = Screen:scaleBySize(100) / 100
    self.font_name = self.font_name or "NotoSansCJKsc-Regular.otf"
    self:rebuild()
    self:readFooter()
    self.visual = self.updates.capture(self.data,self.snapshot,self.page,self.future_page,self.footer)
    self:registerTouchZones({
        { id = "dashboard_tap", ges = "tap", screen_zone = {ratio_x=0,ratio_y=0,ratio_w=1,ratio_h=1},
          handler = function(ges) return self:tap(ges) end },
        { id = "dashboard_swipe", ges = "swipe", screen_zone = {ratio_x=0,ratio_y=0,ratio_w=1,ratio_h=1},
          handler = function(ges) return self:swipe(ges) end },
    })
    self.key_events.Close = { { Device.input.group.Back } }
    self._tick = function() self:tick() end
    self:setAwake(true)
    UIManager:scheduleIn(1, self._tick)
    logger.info("KindleAgentDashboard: view initialized", self.dimen.w, self.dimen.h)
end

function View:rebuild()
    self.data = self.model.build(self.snapshot, os.time(), self.month_offset, self.selected_date, self.countdown_config)
    self.page = math.min(self.page or 0, math.max(0, math.ceil(#self.data.timeline / 6) - 1))
    local display_count = self.selected_date and #self.data.selected or #self.data.future
    self.future_page = math.min(self.future_page or 0, math.max(0, math.ceil(display_count / 5) - 1))
end

function View:displayItems()
    return self.selected_date and self.data.selected or self.data.future
end

function View:readFooter()
    local wifi_ok, wifi = pcall(NetworkMgr.isConnected, NetworkMgr)
    local capacity_ok, capacity = pcall(function() return Device:getPowerDevice():getCapacity() end)
    local icon = "battery"
    if capacity_ok and type(capacity) == "number" then
        icon = capacity > 75 and "battery-full" or capacity > 35 and "battery-medium" or "battery-low"
    end
    self.footer = {wifi=wifi_ok and wifi or false,battery=capacity_ok and capacity or -1,battery_icon=icon}
end

function View:requestUpdates()
    local visual = self.updates.capture(self.data,self.snapshot,self.page,self.future_page,self.footer)
    local changed = self.updates.changed(self.visual,visual)
    self.visual = visual
    if #changed > 0 then
        self.refresh_batches = self.refresh_batches+1
        self.last_refresh = {at=os.time(),mode="ui",regions=changed}
        for _,name in ipairs(changed) do
            local r=self.updates.regions[name]
            -- "ui" does not participate in KOReader's partial→flashing promotion.
            UIManager:setDirty(self,"ui",Geom:new{x=self:px(r[1]),y=self:px(r[2]),w=self:px(r[3]),h=self:px(r[4])})
        end
    end
    self:writeStatus()
end

function View:fullRefresh(reason)
    self.full_refreshes = self.full_refreshes+1
    self.last_refresh = {at=os.time(),mode="full",regions={reason}}
    UIManager:setDirty(self,"full")
end

function View:setAwake(enabled)
    self.keep_awake = enabled
    if not Device:isKindle() then return end
    local powerd = Device:getPowerDevice()
    local handle = powerd.lipc_handle
    if not handle then return end
    if self.old_prevent == nil then
        local ok, value = pcall(handle.get_int_property, handle, "com.lab126.powerd", "preventScreenSaver")
        self.old_prevent = ok and value or 0
    end
    pcall(handle.set_int_property, handle, "com.lab126.powerd", "preventScreenSaver", enabled and 1 or self.old_prevent)
end

function View:px(value) return math.floor(value * self.scale + 0.5) end

function View:text(bb, value, x, y, size, color, width, align)
    local face = Font:getFace(self.font_name, size * self.scale / self.font_scale)
        or Font:getFace("cfont", size * self.scale / self.font_scale)
    local widget = TextWidget:new{ text = str(value, ""), face = face, padding = 0,
        fgcolor = gray(color or 17), max_width = width and self:px(width) or nil }
    local actual = widget:getSize()
    local tx = self:px(x)
    if align == "right" then tx = tx - actual.w end
    if align == "center" then tx = tx - math.floor(actual.w / 2) end
    widget:paintTo(bb, tx, self:px(y))
    widget:free()
end

function View:rect(bb, x, y, w, h, color)
    bb:paintRect(self:px(x), self:px(y), self:px(w), self:px(h), gray(color or 255))
end

function View:line(bb, x, y, x2, color, width)
    self:rect(bb, x, y, x2-x, width or 1, color or 170)
end

function View:icon(bb, name, x, y, size, dim)
    if not name:match("^[a-z-]+$") then name = "cloud" end
    local key = name .. ":" .. size .. ":" .. tostring(dim)
    local widget = self.icons[key]
    if not widget then
        local path = self.plugin_path .. "/icons/" .. name .. ".png"
        local file = io.open(path, "rb")
        if not file then
            path = self.plugin_path .. "/icons/" .. name .. ".svg"
            file = io.open(path, "rb")
        end
        if not file then path = self.plugin_path .. "/icons/cloud.png" else file:close() end
        widget = ImageWidget:new{ file = path, width = self:px(size), height = self:px(size),
            alpha = true, is_icon = true, dim = dim, scale_factor = 0 }
        self.icons[key] = widget
    end
    widget:paintTo(bb, self:px(x), self:px(y))
end

function View:paintTo(bb)
    local ok, err = pcall(self.paintDashboard, self, bb)
    if not ok then
        logger.err("KindleAgentDashboard: render failed", err)
        self.cache.write(self.root .. "/status.json", {active=true,render_error=tostring(err),at=os.time()})
    end
end

function View:paintDashboard(bb)
    local d, s = self.data, self.snapshot
    bb:paintRect(0, 0, self.dimen.w, self.dimen.h, Blitbuffer.COLOR_WHITE)
    self:text(bb, d.clock, 56, 28, 114, 0, 362)
    self:text(bb, d.date_label, 56, 164, 30, 17, 375)
    self:text(bb, d.lunar, 56, 211, 23, 85, 374)
    local weather = type(s.weather) == "table" and s.weather or {}
    self:icon(bb, str(weather.icon, "cloud"), 458, 47, 88)
    self:text(bb, str(weather.location, "--"), 728, 47, 18, 34, 154, "right")
    self:text(bb, number(weather.temperature, "°"), 728, 65, 76, 17, 183, "right")
    local condition = str(weather.condition, "暂无天气")
    self:text(bb, condition .. " · " .. number(weather.low, "°") .. " / " .. number(weather.high, "°"), 728, 164, #condition > 6 and 25 or 30, 51, 292, "right")
    local uv = "--"
    if type(weather.uv) == "number" then uv = weather.uv < 3 and "低" or weather.uv < 6 and "中" or "高" end
    self:text(bb, "雨" .. number(weather.rain_probability, "%") .. " · UV" .. uv .. " · 风" .. number(weather.wind_level, "级"), 728, 211, 23, 85, 294, "right")
    self:line(bb, 56, 270, 728, 17, 4)
    self:rect(bb, 760, 36, 3, 932, 85)
    self:text(bb, "待办事项 & 日程", 56, 322, 34, 17, 421)
    local page_count = math.max(1, math.ceil(#d.timeline / 6))
    self:text(bb, page_count > 1 and ("按时间排序 · " .. (self.page+1) .. "/" .. page_count) or "按时间排序 · 日程与待办", 728, 334, 20, 85, 244, "right")
    if #d.timeline == 0 then
        local source = s.sources or {}
        self:text(bb, (source.calendar and source.calendar.ok) and "今天暂无安排" or "等待同步日程与提醒事项", 112, 395, 28, 85, 605)
    end
    for index = 1, 6 do
        local item = d.timeline[self.page * 6 + index]
        if item then
            local y = 382 + (index - 1) * 94
            if item.kind == "待办" then
                bb:paintBorder(self:px(65), self:px(y+8), self:px(22), self:px(22), self:px(3), gray(51))
            else
                bb:paintCircle(self:px(76), self:px(y+19), self:px(8), gray(51))
            end
            self:text(bb, item.time, 114, y, 25, 51, 85)
            self:text(bb, item.title, 206, y-2, 28, 17, 515)
            self:text(bb, item.kind .. " · " .. meta(item), 206, y+38, 20, 102, 510)
            self:line(bb, 114, y+75, 728, 170)
        end
    end
    local countdown = d.countdown or {}
    self:line(bb, 56, 930, 728, 170, 1)
    if countdown.primary then
        local primary = countdown.primary
        self:text(bb, "倒计时", 56, 940, 20, 102, 120)
        self:text(bb, primary.title, 185, 937, 25, 17, 260)
        self:text(bb, countdown_days(primary), 728, 932, 43, 0, 250, "right")
        self:text(bb, "目标 " .. primary.date, 56, 976, 19, 102, 250)
        for index, item in ipairs(countdown.secondary or {}) do
            -- Keep each auxiliary target on its own row.  The previous
            -- single-line string shared the primary number/date area and
            -- was clipped or visually layered on top of the main target.
            self:text(bb, countdown_secondary_label(item), 728, 978 + (index - 1) * 18, 15, 102, 400, "right")
        end
    else
        self:text(bb, "倒计时", 56, 943, 21, 102, 120)
        self:text(bb, "点击右侧月历日期即可设置目标日", 185, 941, 22, 102, 543)
    end
    self:text(bb, d.month_label, 800, 43, 45, 17, 510)
    self:icon(bb, "settings", 1328, 48, 38)
    local weekdays = {"一", "二", "三", "四", "五", "六", "日"}
    for column, label in ipairs(weekdays) do self:text(bb, label, 800+(column-1)*85+42, 123, 24, 68, 80, "center") end
    for index, cell in ipairs(d.month_cells) do
        local x = 800 + ((index-1) % 7)*85
        local y = 157 + math.floor((index-1)/7)*56
        if cell.is_today then self:rect(bb, x+5, y+1, 75, 52, 17) end
        self:text(bb, cell.day, x+42, y+8, 28, cell.is_today and 255 or cell.in_month and 34 or 170, 70, "center")
        if cell.has_events then bb:paintCircle(self:px(x+42), self:px(y+46), self:px(4), gray(cell.is_today and 255 or 51)) end
        if self.selected_date == cell.date then
            bb:paintBorder(self:px(x+2), self:px(y-1), self:px(81), self:px(56), self:px(3), gray(cell.is_today and 255 or 17))
        end
    end
    self:line(bb, 800, 503, 1400, 68, 2)
    self:text(bb, "节气：" .. str(d.solar_term, "暂无") .. "   下一节气：" .. str(d.next_solar_term, "暂无"), 800, 528, 24, 51, 600)
    local almanac = d.almanac or {}
    self:text(bb, "黄历：宜 " .. short_summary(almanac.yi) .. "   忌 " .. short_summary(almanac.ji), 800, 563, 23, 102, 600)
    self:line(bb, 800, 594, 1400, 170)
    local display = self.selected_date and d.selected or d.future
    local display_title = self.selected_date and (d.selected_label .. "的日程") or "下一周的日程"
    self:text(bb, display_title, 800, 618, 34, 17, 510)
    if self.selected_date then self:text(bb, "点标题返回下一周", 1400, 654, 20, 102, 250, "right") end
    if #display == 0 then self:text(bb, self.selected_date and "当天暂无安排" or "暂无后续安排", 800, 680, 26, 102, 600) end
    for index = 1, 5 do
        local item = display[self.future_page*5 + index]
        if item then
            local y = 671 + (index-1)*67
            self:text(bb, item.date, 800, y, 20, 68, 123)
            self:text(bb, item.time, 923, y, 22, 51, 70)
            self:text(bb, item.title, 993, y-2, 28, 17, 405)
            self:text(bb, item.kind, 1400, y+31, 20, 102, 160, "right")
            self:line(bb, 800, y+58, 1400, 170)
        end
    end
    self:line(bb, 64, 1014, 1384, 68, 2)
    self:icon(bb, "sun", 72, 1021, 30)
    self:icon(bb, self.footer.wifi and "wifi" or "wifi-off", 1288, 1021, 30, not self.footer.wifi)
    self:icon(bb, self.footer.battery_icon, 1344, 1021, 30)
    self.render_count = self.render_count + 1
    self:writeStatus()
end

function View:writeStatus()
    local d,s = self.data,self.snapshot
    local source_status = {}
    for name, source in pairs(s.sources or {}) do
        source_status[name] = {ok=source.ok == true, updated_at=source.updated_at, count=source.count}
    end
    self.cache.write(self.root .. "/status.json", {
        active = true, rendered_at = os.time(), clock = d.clock, date = d.date,
        renders = self.render_count, events = #(s.events or {}), tasks = #(s.tasks or {}),
        timeline = #d.timeline, future = #d.future, page = self.page, future_page=self.future_page,
        month_offset=self.month_offset,month_label=d.month_label,last_refresh=self.last_refresh,
        refresh_batches=self.refresh_batches,full_refreshes=self.full_refreshes,
        width = self.dimen.w, height = self.dimen.h, battery = self.footer.battery,
        wifi = self.footer.wifi, sync_error = self.client.error or "",
        snapshot_at = s.generated_at or 0, sources = source_status,
        countdown = d.countdown,
    })
end

function View:saveCountdownConfig(config)
    self.countdown_config = config
    self.cache.write(self.countdown_path, config)
    self:rebuild()
    self:requestUpdates()
end

function View:setPrimaryCountdown(date, title)
    local config = self.countdown_config or {version=1, primary_id="primary", targets={}}
    config.version = 1
    config.primary_id = "primary"
    config.targets = type(config.targets) == "table" and config.targets or {}
    local found = false
    for _, target in ipairs(config.targets) do
        if target.id == "primary" then
            target.date = date
            target.enabled = true
            target.title = title or target.title or "目标日"
            found = true
            break
        end
    end
    if not found then
        config.targets[#config.targets + 1] = {id="primary", title=title or "目标日", date=date, enabled=true}
    end
    self:saveCountdownConfig(config)
end

function View:addCountdownTarget(date, title)
    local config = self.countdown_config or {version=1, primary_id="primary", targets={}}
    config.version = 1
    config.targets = type(config.targets) == "table" and config.targets or {}
    config.targets[#config.targets + 1] = {
        id = "target-" .. tostring(os.time()) .. "-" .. tostring(#config.targets + 1),
        title = title ~= "" and title or "目标日",
        date = date,
        enabled = true,
    }
    self:saveCountdownConfig(config)
end

function View:clearPrimaryCountdown()
    local config = self.countdown_config or {version=1, primary_id="primary", targets={}}
    local kept = {}
    for _, target in ipairs(config.targets or {}) do
        if target.id ~= "primary" then kept[#kept + 1] = target end
    end
    config.targets = kept
    self:saveCountdownConfig(config)
end

function View:scheduleActions(item)
    local date = item and item.target_date
    if type(date) ~= "string" or date == "" then
        UIManager:show(require("ui/widget/infomessage"):new{text="这个日程没有可用的目标日期。"})
        return
    end
    local title = str(item.title, "目标日")
    local dialog
    local close = function() if dialog then UIManager:close(dialog) end end
    local buttons = {
        {{text="设为主倒计时", callback=function()
            close(); self:setPrimaryCountdown(date, title)
        end}, {text="新增倒计时", callback=function()
            close(); self:addCountdownTarget(date, title)
        end}},
        {{text="取消", callback=close}},
    }
    local display_date = item.date or date
    -- The dialog is opened from the calendar tap handler.  If it remains
    -- dismissable, KOReader can deliver the schedule tap to the dialog's
    -- full-screen TapClose range and immediately close it again.  Keep an
    -- explicit 取消 button instead, so the first tap reliably leaves the
    -- action menu visible.
    dialog = require("ui/widget/buttondialog"):new{
        title=display_date .. " · " .. title,
        buttons=buttons,
        dismissable=false,
    }
    UIManager:show(dialog)
end

function View:tap(ges)
    local x, y = ges.pos.x / self.scale, ges.pos.y / self.scale
    if x >= 1295 and y < 114 then self:settings(); return true end
    if x >= 800 and y < 114 then self:setMonth(0); return true end
    if x < 150 and y > 995 then self:brightness(); return true end
    if x >= 800 and y >= 600 and y < 670 then
        self:setSelectedDate(nil)
        return true
    end
    if x >= 800 and y >= 145 and y < 505 then
        local column = math.floor((x - 800) / 85)
        local row = math.floor((y - 157) / 56)
        if column >= 0 and column < 7 and row >= 0 and row < 6 then
            local cell = self.data.month_cells[row * 7 + column + 1]
            if cell then
                local same_selected = self.selected_date == cell.date
                self:setSelectedDate(same_selected and nil or cell.date)
                return true
            end
        end
    end
    if x >= 800 and y >= 508 and y < 595 then
        local a = self.data.almanac or {}
        UIManager:show(require("ui/widget/infomessage"):new{
            text = "黄历（传统民俗参考）\n\n宜：" .. summary(a.yi) .. "\n\n忌：" .. summary(a.ji),
        })
        return true
    end
    if x >= 800 and y >= 670 and y < 1008 then
        local display = self:displayItems()
        local item = display[self.future_page*5 + math.floor((y-670)/67) + 1]
        if item then self:scheduleActions(item) end
        return true
    end
    if x < 760 and y >= 376 and y <= 944 then
        local index = math.floor((y-376)/94) + 1
        local item = self.data.timeline[self.page*6 + index]
        if item then
            UIManager:show(require("ui/widget/infomessage"):new{
                text = item.time .. "  " .. item.title .. "\n\n" .. item.kind .. " · " .. meta(item),
            })
        end
    end
    return true
end

function View:setMonth(offset)
    local candidate = self.model.build(self.snapshot,os.time(),offset,self.selected_date,self.countdown_config)
    local key = string.format("%04d-%02d-01",candidate.calendar_year,candidate.calendar_month)
    local first,last = self.snapshot.range_start,self.snapshot.range_end
    if type(first)=="string" and type(last)=="string" and (key<first or key>=last) then
        UIManager:show(require("ui/widget/infomessage"):new{
            text="目前已同步前两个月、当月和后两个月的日程。\n点月份标题可回到当月。",
        })
        return
    end
    self.month_offset=offset
    self.data=candidate
    self:requestUpdates()
end

function View:setSelectedDate(date)
    self.selected_date = date
    self.future_page = 0
    self:rebuild()
    self:requestUpdates()
end

function View:swipe(ges)
    local delta=({north=1,west=1,south=-1,east=-1})[ges.direction]
    if not delta then return true end
    local x,y=ges.pos.x/self.scale,ges.pos.y/self.scale
    if x>=760 and y>=145 and y<505 then
        self:setMonth(self.month_offset+delta)
        return true
    elseif x<760 and y>=310 and y<950 then
        self.page = (self.page + delta) % math.max(1, math.ceil(#self.data.timeline/6))
    elseif x>=760 and y>=608 and y<1014 then
        local display_count = self.selected_date and #self.data.selected or #self.data.future
        self.future_page = (self.future_page + delta) % math.max(1, math.ceil(display_count/5))
    end
    self:requestUpdates()
    return true
end

function View:brightness()
    local ok, widget = pcall(function() return require("ui/widget/frontlightwidget"):new{} end)
    if ok then UIManager:show(widget) else logger.warn("KindleAgentDashboard: frontlight unavailable") end
end

function View:settings()
    local dialog
    local function close() if dialog then UIManager:close(dialog) end end
    local function status()
        close()
        local lines = { "同步状态" }
        for _, name in ipairs({"calendar", "reminders", "weather"}) do
            local item = (self.snapshot.sources or {})[name] or {}
            local label = ({calendar="日历",reminders="提醒事项",weather="天气"})[name]
            local at = type(item.updated_at) == "number" and os.date("!%m-%d %H:%M", item.updated_at + 28800) or "尚未同步"
            lines[#lines+1] = label .. "：" .. (item.ok and "正常" or "未更新") .. " · " .. at
        end
        lines[#lines+1] = self.client.error or ""
        UIManager:show(require("ui/widget/infomessage"):new{text = table.concat(lines, "\n")})
    end
    dialog = require("ui/widget/buttondialog"):new{
        title = "Kindle Agent 看板", buttons = {
            {{text="立即同步", callback=function() close(); self.last_request=0; self:tick(true) end}, {text="同步状态", callback=status}},
            {{text="亮度调节", callback=function() close(); self:brightness() end}, {text=self.keep_awake and "关闭常显" or "开启常显", callback=function() self:setAwake(not self.keep_awake); close() end}},
            {{text="清除残影", callback=function() close(); self:fullRefresh("manual") end}, {text="回到当月", callback=function() close(); self:setMonth(0) end}},
            {{text="返回看板", callback=close}, {text="退出看板", callback=function() close(); self:onClose() end}},
        },
    }
    UIManager:show(dialog)
end

function View:tick(immediate)
    if self.closed then return end
    if not immediate then UIManager:scheduleIn(2, self._tick) end
    if self.suspended then return end
    local result = self.client:poll()
    local synced = type(result) == "table"
    if synced then self.snapshot = result end
    local now = os.time()
    if now - self.last_request >= 60 then self.last_request = now; self.client:start() end
    local new_minute = self.data.clock ~= os.date("!%H:%M", now + (self.snapshot.utc_offset or 28800))
    local poll_device = now-self.last_device_poll>=30
    if poll_device then self:readFooter(); self.last_device_poll=now end
    if synced or new_minute then
        self:rebuild()
    end
    if synced or new_minute or poll_device then self:requestUpdates()
    elseif result==false then self:writeStatus() end
end

function View:onSuspend()
    self.suspended = true
    self.client:stop()
    self.was_awake = self.keep_awake
    self:setAwake(false)
end

function View:onResume()
    self.suspended = false
    if self.was_awake then self:setAwake(true) end
    self.last_request = 0
    self:rebuild()
    self:readFooter()
    self.visual=self.updates.capture(self.data,self.snapshot,self.page,self.future_page,self.footer)
    self:fullRefresh("resume")
end

function View:onClose()
    if self.closed then return true end
    UIManager:close(self)
    return true
end

function View:onCloseWidget()
    if self.closed then return end
    self.closed = true
    UIManager:unschedule(self._tick)
    self.client:stop()
    self:setAwake(false)
    for _, widget in pairs(self.icons) do widget:free() end
    self.cache.write(self.root .. "/status.json", {active=false,closed_at=os.time()})
    if self.owner then self.owner.view = nil end
    if self.previous_rotation ~= nil and Screen:getRotationMode() ~= self.previous_rotation then
        UIManager:broadcastEvent(require("ui/event"):new("SetRotationMode", self.previous_rotation))
    end
    UIManager:setDirty("all", "full")
    logger.info("KindleAgentDashboard: closed cleanly")
end

return View
