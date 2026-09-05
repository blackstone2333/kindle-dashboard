local model = dofile(arg[1] or "device/koreader/plugins/kindleagentdashboard.koplugin/model.lua")

local function assert_true(condition, message)
    if not condition then
        error(message or "assertion failed")
    end
end

local function assert_eq(actual, expected, message)
    if actual ~= expected then
        error((message or "assertion failed") .. ": expected " .. tostring(expected) .. ", got " .. tostring(actual))
    end
end

local function run(name, fn)
    local ok, err = pcall(fn)
    if ok then
        print("PASS", name)
        return true, nil
    else
        print("FAIL", name, err)
        return false, err
    end
end

local function has_entry(items, predicate)
    for _, item in ipairs(items) do
        if predicate(item) then
            return true
        end
    end
    return false
end

local function build_days(date)
    return {
        [date] = {
            lunar = "农历示例",
            solar_term = "处暑",
            next_solar_term = "白露",
            almanac = {yi = "宜", ji = "忌"},
        },
    }
end

-- 1) month grid: 42 cells, leap day coverage, and month-end day exists.
local failures = 0

local function execute(name, fn)
    local ok, _ = run(name, fn)
    if not ok then
        failures = failures + 1
    end
end

execute("month grid + leap support", function()
    local now = 1711857600 -- 2024-03-31 12:00 +08:00
    local out = model.build({
        utc_offset = 28800,
        days = build_days("2024-03-31"),
        events = {},
        tasks = {},
    }, now)

    assert_eq(out.date, "2024-03-31", "date")
    assert_eq(#out.month_cells, 42, "month cells count")
    assert_true(has_entry(out.month_cells, function(item)
        return item.date == "2024-03-31" and item.in_month
    end), "march month end cell")
    assert_true(has_entry(out.month_cells, function(item)
        return item.date == "2024-02-29" and not item.in_month
    end), "2024-02-29 should appear in 6-week grid")
end)

-- 2) UTC+8 midnight boundary
execute("dateKey midnight boundary", function()
    local now = 1788537600 -- 2026-09-05 00:00 +08:00
    local out = model.build({
        utc_offset = 28800,
        days = build_days("2026-09-05"),
        events = {},
        tasks = {},
    }, now)

    assert_eq(model.dateKey(now, 28800), "2026-09-05")
    assert_eq(out.date, "2026-09-05")
    assert_eq(out.clock, "00:00")
    assert_eq(out.date_label, "2026年9月5日  星期六")
    assert_true(out.date_label:find("星期六") ~= nil)
    assert_eq(out.month_label, "2026年9月")
end)

execute("weekday labels are Monday-first", function()
    local out = model.build({
        utc_offset = 28800,
        days = build_days("2026-09-07"),
        events = {},
        tasks = {},
    }, 1788710400) -- 2026-09-07 00:00 +08:00

    assert_eq(out.date_label, "2026年9月7日  星期一")
end)

-- 3) all-day exclusive end, do not spill to next local midnight.
execute("all-day event exclusive end", function()
    local now = 1788572400 -- 2026-09-05 09:00 +08:00
    local out = model.build({
        utc_offset = 28800,
        days = build_days("2026-09-05"),
        events = {
            {
                id = "all-day",
                title = "全天事件",
                start = 1788537600, -- 2026-09-05 00:00 +08:00
                ["end"] = 1788624000, -- 2026-09-06 00:00 +08:00
                all_day = true,
            },
        },
        tasks = {},
    }, now)

    assert_eq(out.timeline[1].time, "全天")
    assert_eq(out.timeline[1].kind, "日程")
    assert_true(has_entry(out.month_cells, function(item)
        return item.date == "2026-09-05" and item.has_events
    end), "event-day should have dot")
    assert_true(has_entry(out.month_cells, function(item)
        return item.date == "2026-09-06" and not item.has_events
    end), "exclusive end should not mark next day")
end)

-- 4) many items retained (no truncation)
execute("many items retained", function()
    local now = 1711861200 -- 2024-03-31 13:00 +08:00
    local events = {}
    local tasks = {}
    for idx = 1, 30 do
        table.insert(events, {
            id = "ev" .. idx,
            title = "event-" .. idx,
            start = now + (idx * 60),
            ["end"] = now + (idx * 60) + 1200,
            all_day = false,
        })
    end
    for idx = 1, 30 do
        table.insert(tasks, {
            id = "ta" .. idx,
            title = "task-" .. idx,
            due = now + (idx * 90),
            has_time = true,
        })
    end

    local out = model.build({
        utc_offset = 28800,
        days = build_days("2024-03-31"),
        events = events,
        tasks = tasks,
    }, now)

    assert_eq(#out.timeline, 60)
end)

-- 5) canceled events and completed tasks excluded
execute("timed events and tasks share chronological order", function()
    local now = 1788572400
    local out = model.build({events={
        {id="late", title="日程", start=now+3600, ["end"]=now+7200},
    }, tasks={
        {id="early", title="待办", due=now+60, has_time=true},
    }}, now)
    assert_eq(out.timeline[1].id, "task:early")
    assert_eq(out.timeline[2].id, "event:late")
end)

execute("canceled/completed excluded", function()
    local now = 1711861200 -- 2024-03-31 13:00 +08:00
    local out = model.build({
        utc_offset = 28800,
        days = build_days("2024-03-31"),
        events = {
            {id = "ok", title = "正常", start = now + 100, ["end"] = now + 200},
            {id = "bad", title = "取消", start = now + 300, ["end"] = now + 400, status = "canceled"},
        },
        tasks = {
            {id = "task-ok", title = "有效", due = now + 100, has_time = true},
            {id = "task-bad", title = "完成", due = now + 200, has_time = true, completed = true},
        },
    }, now)

    assert_eq(#out.timeline, 2)
    assert_true(not has_entry(out.timeline, function(item) return item.id == "event:bad" end), "canceled event should be skipped")
    assert_true(not has_entry(out.timeline, function(item) return item.id == "task:task-bad" end), "completed task should be skipped")
end)

-- 6) undated included and overdue visible
execute("undated and overdue tasks", function()
    local now = 1788572400 -- 2026-09-05 09:00 +08:00
    local out = model.build({
        utc_offset = 28800,
        days = build_days("2026-09-05"),
        events = {},
        tasks = {
            {id = "overdue", title = "逾期待办", due_date = "2026-09-04", has_time = false},
            {id = "today", title = "今日待办", due_date = "2026-09-05", has_time = false},
            {id = "undated", title = "无日期", has_time = false},
        },
    }, now)

    local mapping = {}
    local position = {}
    for idx, item in ipairs(out.timeline) do
        local raw = item.id:gsub("^task:", "")
        mapping[raw] = item.time
        position[raw] = idx
    end

    assert_eq(mapping.overdue, "逾期")
    assert_eq(mapping.today, "未定时")
    assert_eq(mapping.undated, "未定时")
    assert_true(position.today < position.overdue)
    assert_true(position.overdue < position.undated)
end)

-- 7) overlapping midnight future occurrences and dedupe
execute("overlapping midnight spans", function()
    local now = 1788622200 -- 2026-09-05 23:30 +08:00
    local out_first = model.build({
        utc_offset = 28800,
        days = build_days("2026-09-05"),
        events = {
            {
                id = "midnight",
                title = "跨午夜",
                start = 1788622200,
                ["end"] = 1788625800,
            }
        },
        tasks = {},
    }, now)

    assert_eq(#out_first.timeline, 1)
    assert_eq(out_first.timeline[1].time, "23:30")
    local future_hits = 0
    for _, item in ipairs(out_first.future) do
        if item.id == "event:midnight" then
            future_hits = future_hits + 1
            assert_eq(item.date, "09月05日 六")
            assert_eq(item.time, "23:30")
        end
    end
    assert_eq(future_hits, 1)

    local out_next = model.build({
        utc_offset = 28800,
        days = build_days("2026-09-06"),
        events = {
            {
                id = "midnight",
                title = "跨午夜",
                start = 1788622200,
                ["end"] = 1788625800,
            }
        },
        tasks = {},
    }, 1788624900) -- 2026-09-06 00:15 +08:00

    assert_eq(#out_next.timeline, 1)
    assert_eq(out_next.timeline[1].time, "23:30")
end)

execute("selected calendar day builds its own schedule", function()
    local now = 1788572400 -- 2026-09-05 09:00 +08:00
    local out = model.build({
        utc_offset = 28800,
        events = {{id="later", title="周日会议", start=1788710400+3600, ["end"]=1788710400+7200}},
        tasks = {{id="later-task", title="周日待办", due_date="2026-09-07", has_time=false}},
    }, now, 0, "2026-09-07")
    assert_eq(out.selected_label, "09月07日")
    assert_eq(#out.selected, 2)
    assert_eq(out.selected[1].title, "周日会议")
    assert_eq(out.selected[2].title, "周日待办")
end)

if failures > 0 then
    io.stderr:write("device model tests failed: " .. failures .. "\n")
    os.exit(1)
end
