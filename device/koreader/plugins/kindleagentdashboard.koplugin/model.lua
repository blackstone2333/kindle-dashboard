local M = {}

local DAY_SECONDS = 24 * 60 * 60
local DEFAULT_OFFSET = 28800

local WEEKDAY_FULL = {
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
}

local WEEKDAY_SHORT = {
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "日",
}

local function as_number(value)
    if type(value) ~= "number" then
        return nil
    end
    if value ~= value or value == math.huge or value == -math.huge then
        return nil
    end
    return value
end

local function as_bool(value)
    if value == true or value == 1 or value == "1" then
        return true
    end
    if value == false or value == 0 or value == "0" or value == nil then
        return false
    end
    return tostring(value) == "true"
end

local function as_string(value)
    if value == nil then
        return nil
    end
    if type(value) == "string" then
        return value
    end
    if type(value) == "number" or type(value) == "boolean" then
        return tostring(value)
    end
    return nil
end

local function trim(value)
    if type(value) ~= "string" then
        return value == nil and "" or tostring(value)
    end
    local text = value:gsub("^%s+", ""):gsub("%s+$", "")
    return text
end

local function copy_table(source)
    if type(source) ~= "table" then
        return {}
    end
    local target = {}
    for key, value in pairs(source) do
        target[key] = value
    end
    return target
end

-- Convert a local day number (1970-01-01 is day 0) to calendar date.
local function date_from_day(day_number)
    local z = day_number + 719468
    local era = math.floor(z / 146097)
    local doe = z - era * 146097
    local yoe = math.floor((doe - math.floor(doe / 1460) + math.floor(doe / 36524) - math.floor(doe / 146096)) / 365)
    local doy = doe - (365 * yoe + math.floor(yoe / 4) - math.floor(yoe / 100) + math.floor(yoe / 400))
    local mp = math.floor((5 * doy + 2) / 153)
    local day = doy - math.floor((153 * mp + 2) / 5) + 1
    local month = mp + (mp < 10 and 3 or -9)
    local year = yoe + era * 400
    if month <= 2 then
        year = year + 1
    end
    return year, month, day
end

local function day_from_date(year, month, day)
    local y = tonumber(year)
    local m = tonumber(month)
    local d = tonumber(day)
    if not y or not m or not d then
        return nil
    end
    local yy = y - (m <= 2 and 1 or 0)
    local mm = m > 2 and (m - 3) or (m + 9)
    local n = d - 1 + math.floor((153 * mm + 2) / 5) + 365 * yy + math.floor(yy / 4) - math.floor(yy / 100) + math.floor(yy / 400) - 719468
    return n
end

local function day_key_from_day(day_number)
    local year, month, day = date_from_day(day_number)
    return string.format("%04d-%02d-%02d", year, month, day)
end

local function parse_ymd(value)
    if type(value) ~= "string" then
        return nil
    end
    local year, month, day = value:match("^(%d+)%-(%d+)%-(%d+)$")
    if not year then
        return nil
    end
    return day_from_date(tonumber(year), tonumber(month), tonumber(day))
end

local function local_day_number(epoch_seconds, offset)
    local epoch = as_number(epoch_seconds)
    if not epoch then
        return nil
    end
    local zone = as_number(offset)
    if not zone then
        zone = DEFAULT_OFFSET
    end
    return math.floor((epoch + zone) / DAY_SECONDS)
end

local function day_start_epoch(day_number, offset)
    local zone = as_number(offset)
    if not zone then
        zone = DEFAULT_OFFSET
    end
    return day_number * DAY_SECONDS - zone
end

local function format_clock(epoch_seconds, offset)
    local epoch = as_number(epoch_seconds)
    if not epoch then
        return "--:--"
    end
    local zone = as_number(offset)
    if not zone then
        zone = DEFAULT_OFFSET
    end
    local local_time = os.date("!*t", epoch + zone)
    return string.format("%02d:%02d", local_time.hour, local_time.min)
end

function M.dateKey(epoch, offset)
    local zone = as_number(offset)
    if not zone then
        zone = DEFAULT_OFFSET
    end
    local epoch_seconds = as_number(epoch)
    if not epoch_seconds then
        epoch_seconds = 0
    end
    local local_time = os.date("!*t", epoch_seconds + zone)
    return string.format("%04d-%02d-%02d", local_time.year, local_time.month, local_time.day)
end

local function countdown_target(target, today_day)
    if type(target) ~= "table" or target.enabled == false then
        return nil
    end
    local target_date = as_string(target.date) or as_string(target.target_date)
    local target_day = parse_ymd(target_date)
    if not target_day then
        return nil
    end
    local days = target_day - today_day
    local state = days > 0 and "upcoming" or days == 0 and "today" or "past"
    return {
        id = as_string(target.id) or target_date,
        title = trim(as_string(target.title) or "目标日"),
        date = target_date,
        days = days,
        state = state,
    }
end

local function build_countdown(config, today_day)
    local result = {enabled = false, primary = nil, secondary = {}, count = 0}
    if type(config) ~= "table" or type(config.targets) ~= "table" then
        return result
    end
    local primary_id = as_string(config.primary_id) or "primary"
    local targets = {}
    for _, raw in ipairs(config.targets) do
        local target = countdown_target(raw, today_day)
        if target then
            targets[#targets + 1] = target
        end
    end
    table.sort(targets, function(a, b)
        if a.id == primary_id and b.id ~= primary_id then return true end
        if b.id == primary_id and a.id ~= primary_id then return false end
        if a.days ~= b.days then return a.days < b.days end
        return a.id < b.id
    end)
    result.count = #targets
    result.enabled = #targets > 0
    result.primary = targets[1]
    for index = 2, math.min(#targets, 3) do
        result.secondary[#result.secondary + 1] = targets[index]
    end
    return result
end

local function parse_event(item, index)
    if type(item) ~= "table" then
        return nil
    end

    local status = as_string(item.status)
    if status then
        local lower = status:lower()
        if lower == "cancelled" or lower == "canceled" then
            return nil
        end
    end

    local start = as_number(item.start)
    local stop = as_number(item["end"])
    if not start or not stop then
        return nil
    end
    if stop < start then
        start, stop = stop, start
    end
    if stop == start then
        return nil
    end

    local id = trim(item.id)
    if id == "" then
        id = tostring(index)
    end

    return {
        id = id,
        title = trim(item.title),
        start = start,
        stop = stop,
        all_day = as_bool(item.all_day),
        calendar = item.calendar,
        location = item.location,
        meta = copy_table(item),
    }
end

local function parse_task(item, index)
    if type(item) ~= "table" then
        return nil
    end

    if as_bool(item.completed) then
        return nil
    end

    local status = as_string(item.status)
    if status then
        local lower = status:lower()
        if lower == "cancelled" or lower == "canceled" then
            return nil
        end
    end

    local id = trim(item.id)
    if id == "" then
        id = tostring(index)
    end

    return {
        id = id,
        title = trim(item.title),
        due = as_number(item.due),
        due_date = as_string(item.due_date),
        has_time = as_bool(item.has_time),
        meta = copy_table(item),
    }
end

local function build_timeline_event(event, day_start, offset)
    local item = {
        id = "event:" .. event.id,
        title = event.title,
        kind = "日程",
        meta = event.meta,
        sort_epoch = event.all_day and day_start or event.start,
        all_day = event.all_day,
        order = event.all_day and 0 or 1,
    }
    item.time = event.all_day and "全天" or format_clock(event.start, offset)
    return item
end

local function build_timeline_task(task, now_day_number, offset)
    local sort_epoch = as_number(task.due)
    local due_day = nil
    local time_label = "未定时"
    local order = 4
    local overdue = false

    if task.has_time and sort_epoch then
        local due_start_day = local_day_number(sort_epoch, offset)
        if due_start_day == now_day_number then
            time_label = format_clock(sort_epoch, offset)
            order = 1
            due_day = due_start_day
        elseif due_start_day and due_start_day < now_day_number then
            overdue = true
            time_label = "逾期"
            order = 3
            due_day = due_start_day
        end
    elseif task.due_date then
        due_day = parse_ymd(task.due_date)
        if due_day then
            if due_day == now_day_number then
                time_label = "未定时"
                order = 2
            elseif due_day < now_day_number then
                overdue = true
                time_label = "逾期"
                order = 3
            end
        end
    elseif not task.has_time and sort_epoch then
        due_day = local_day_number(sort_epoch, offset)
        if due_day and due_day == now_day_number then
            order = 2
        elseif due_day and due_day < now_day_number then
            overdue = true
            time_label = "逾期"
            order = 3
        end
    end

    if overdue == false and due_day == nil and not task.due_date then
        if not task.has_time then
            order = 4
            time_label = "未定时"
        else
            return nil
        end
    end

    if overdue or due_day == now_day_number or (not task.has_time and not task.due_date and not sort_epoch) then
        return {
            id = "task:" .. task.id,
            title = task.title,
            kind = "待办",
            time = time_label,
            meta = task.meta,
            sort_epoch = sort_epoch,
            order = order,
        }
    end
    return nil
end

local function timeline_comparator(a, b)
    if a.order ~= b.order then
        return a.order < b.order
    end
    if a.order == 2 or a.order == 3 then
        if a.time ~= b.time then
            return a.time < b.time
        end
    end
    local a_sort = a.sort_epoch
    local b_sort = b.sort_epoch
    if a_sort == nil then
        a_sort = math.huge
    end
    if b_sort == nil then
        b_sort = math.huge
    end
    if a_sort ~= b_sort then
        return a_sort < b_sort
    end
    if a.title ~= b.title then
        return a.title < b.title
    end
    return tostring(a.id) < tostring(b.id)
end

local function agent_cards(snapshot, now_epoch)
    local result = {}
    local cards = type(snapshot.cards) == "table" and snapshot.cards or {}
    for _, card in ipairs(cards) do
        if type(card) == "table" and type(card.title) == "string" and card.title ~= "" then
            local expires_at = tonumber(card.expires_at)
            if not expires_at or expires_at > now_epoch then
                result[#result + 1] = {
                    id = tostring(card.id or #result + 1),
                    type = tostring(card.type or "briefing"),
                    title = card.title,
                    body = type(card.body) == "string" and card.body or "",
                    symbol = type(card.symbol) == "string" and card.symbol or nil,
                    source_url = type(card.source_url) == "string" and card.source_url or nil,
                    generated_at = tonumber(card.generated_at) or 0,
                    priority = tonumber(card.priority) or 0,
                }
            end
        end
    end
    table.sort(result, function(a, b)
        if a.priority ~= b.priority then return a.priority > b.priority end
        return a.id < b.id
    end)
    return result
end

function M.build(snapshot, now_epoch, month_offset, selected_date, countdown_config, week_offset)
    local source = (type(snapshot) == "table") and snapshot or {}
    local offset = as_number(source.utc_offset) or DEFAULT_OFFSET
    local epoch_now = as_number(now_epoch) or os.time()
    local now_day = local_day_number(epoch_now, offset)

    local date = M.dateKey(epoch_now, offset)
    local now_year, now_month, now_day_of_month = date_from_day(now_day)
    local wday_index = ((now_day + 3) % 7) + 1

    local day_key = day_key_from_day(now_day)
    local day_meta = (type(source.days) == "table" and source.days[day_key]) or {}

    local today_start = day_start_epoch(now_day, offset)
    local today_end = today_start + DAY_SECONDS

    local events = (type(source.events) == "table") and source.events or {}
    local tasks = (type(source.tasks) == "table") and source.tasks or {}

    local normalized_events = {}
    for index, raw in ipairs(events) do
        local item = parse_event(raw, index)
        if item then
            table.insert(normalized_events, item)
        end
    end

    local normalized_tasks = {}
    for index, raw in ipairs(tasks) do
        local item = parse_task(raw, index)
        if item then
            table.insert(normalized_tasks, item)
        end
    end

    local timeline = {}
    for _, item in ipairs(normalized_events) do
        if item.start < today_end and item.stop > today_start then
            local overlap = false
            local stop_day = local_day_number(item.stop - 1, offset)
            for day = local_day_number(item.start, offset), stop_day do
                if day == now_day then
                    overlap = true
                end
            end
            if overlap then
                table.insert(timeline, build_timeline_event(item, today_start, offset))
            end
        end
    end

    for _, task in ipairs(normalized_tasks) do
        local item = build_timeline_task(task, now_day, offset)
        if item then
            table.insert(timeline, item)
        end
    end

    table.sort(timeline, timeline_comparator)

    local future = {}
    local future_seen = {}
    local future_start = now_day + (math.floor(as_number(week_offset) or 0) * 7)
    local future_limit = future_start + 6

    for _, event in ipairs(normalized_events) do
        local start_day = local_day_number(event.start, offset)
        local end_day = local_day_number(event.stop - 1, offset)
        local event_day = nil
        for day = future_start, future_limit do
            if day >= start_day and day <= end_day then
                event_day = day
                break
            end
        end
        if event_day then
            local id = "event:" .. event.id
            if not future_seen[id] then
                local _, ev_month, ev_day = date_from_day(event_day)
                local e = {
                    id = id,
                    title = event.title,
                    date = string.format("%02d月%02d日 %s", ev_month, ev_day, WEEKDAY_SHORT[((event_day + 3) % 7) + 1]),
                    target_date = day_key_from_day(event_day),
                    time = event.all_day and "全天" or format_clock(event.start, offset),
                    kind = "日程",
                    meta = event.meta,
                    sort_epoch = event.start,
                    _day = event_day,
                }
                future_seen[id] = true
                table.insert(future, e)
            end
        end
    end

    for _, task in ipairs(normalized_tasks) do
        if task.due then
            local due_day = local_day_number(task.due, offset)
            if due_day and due_day >= future_start and due_day <= future_limit then
                local id = "task:" .. task.id
                local due_time = task.has_time and format_clock(task.due, offset) or "未定时"
                local _, ev_month, ev_day = date_from_day(due_day)
                local due_entry = {
                    id = id,
                    title = task.title,
                    date = string.format("%02d月%02d日 %s", ev_month, ev_day, WEEKDAY_SHORT[((due_day + 3) % 7) + 1]),
                    target_date = day_key_from_day(due_day),
                    time = due_time,
                    kind = "待办",
                    meta = task.meta,
                    sort_epoch = task.due,
                    _day = due_day,
                }
                table.insert(future, due_entry)
            end
        elseif task.due_date then
            local due_day = parse_ymd(task.due_date)
            if due_day and due_day >= future_start and due_day <= future_limit then
                local id = "task:" .. task.id
                local _, ev_month, ev_day = date_from_day(due_day)
                table.insert(future, {
                    id = id,
                    title = task.title,
                    date = string.format("%02d月%02d日 %s", ev_month, ev_day, WEEKDAY_SHORT[((due_day + 3) % 7) + 1]),
                    target_date = day_key_from_day(due_day),
                    time = "未定时",
                    kind = "待办",
                    meta = task.meta,
                    sort_epoch = task.due,
                    _day = due_day,
                })
            end
        end
    end

    table.sort(future, function(a, b)
        if a._day ~= b._day then
            return a._day < b._day
        end
        local a_epoch = a.sort_epoch or 0
        local b_epoch = b.sort_epoch or 0
        if a_epoch ~= b_epoch then
            return a_epoch < b_epoch
        end
        if a.kind ~= b.kind then
            return a.kind < b.kind
        end
        if a.time ~= b.time then
            return a.time < b.time
        end
        return tostring(a.id) < tostring(b.id)
    end)

    for _, item in ipairs(future) do
        item._day = nil
    end

    local selected = future
    local selected_label = nil
    if type(selected_date) == "string" then
        local selected_day_number = parse_ymd(selected_date)
        if selected_day_number then
            local _, selected_month, selected_dom = date_from_day(selected_day_number)
            selected_label = string.format("%02d月%02d日", selected_month, selected_dom)
            selected = {}
            for _, event in ipairs(normalized_events) do
                local start_day = local_day_number(event.start, offset)
                local end_day = local_day_number(event.stop - 1, offset)
                if start_day and end_day and selected_day_number >= start_day and selected_day_number <= end_day then
                    local item = build_timeline_event(event, day_start_epoch(selected_day_number, offset), offset)
                    item.date = selected_label
                    item.target_date = selected_date
                    item._day = selected_day_number
                    table.insert(selected, item)
                end
            end
            for _, task in ipairs(normalized_tasks) do
                local due_day = task.due and local_day_number(task.due, offset) or parse_ymd(task.due_date)
                if due_day == selected_day_number then
                    table.insert(selected, {
                        id = "task:" .. task.id, title = task.title, kind = "待办",
                        date = selected_label, target_date = selected_date,
                        time = task.has_time and format_clock(task.due, offset) or "未定时",
                        meta = task.meta, sort_epoch = task.due or day_start_epoch(selected_day_number, offset),
                        order = task.has_time and 2 or 4, _day = selected_day_number,
                    })
                end
            end
            table.sort(selected, timeline_comparator)
            for _, item in ipairs(selected) do item._day = nil end
        end
    end

    local display_month_number = now_year*12 + now_month-1 + math.floor(as_number(month_offset) or 0)
    local display_year = math.floor(display_month_number/12)
    local display_month = display_month_number%12+1
    local first_day_in_month = day_from_date(display_year, display_month, 1)
    local first_weekday = ((first_day_in_month + 3) % 7) + 1
    local grid_start = first_day_in_month - (first_weekday - 1)

    local month_cells = {}
    local month_events = {}

    for _, item in ipairs(normalized_events) do
        local start_day = local_day_number(item.start, offset)
        local end_day = local_day_number(item.stop - 1, offset)
        for day = start_day, end_day do
            local key = day_key_from_day(day)
            month_events[key] = true
        end
    end

    for index = 0, 41 do
        local day_number = grid_start + index
        local year, month, day = date_from_day(day_number)
        local key = day_key_from_day(day_number)
        table.insert(month_cells, {
            date = key,
            day = day,
            in_month = (month == display_month and year == display_year),
            is_today = (day_number == now_day),
            has_events = month_events[key] == true,
            _day = day_number,
        })
    end

    for _, item in ipairs(month_cells) do
        item._day = nil
    end

    local day_meta_lunar = (type(day_meta) == "table" and day_meta.lunar) and day_meta.lunar or "农历暂无"
    local day_meta_almanac = (type(day_meta) == "table" and type(day_meta.almanac) == "table") and day_meta.almanac or nil

    return {
        clock = format_clock(epoch_now, offset),
        date = date,
        date_label = string.format("%d年%d月%d日  %s", now_year, now_month, now_day_of_month, WEEKDAY_FULL[wday_index]),
        year = now_year,
        month = now_month,
        day = now_day_of_month,
        month_label = string.format("%d年%d月", display_year, display_month),
        calendar_year = display_year,
        calendar_month = display_month,
        lunar = day_meta_lunar,
        solar_term = (type(day_meta) == "table" and day_meta.solar_term) or "暂无",
        solar_term_date = (type(day_meta) == "table" and day_meta.solar_term_date) or "暂无",
        next_solar_term = (type(day_meta) == "table" and day_meta.next_solar_term) or "暂无",
        next_solar_term_date = (type(day_meta) == "table" and day_meta.next_solar_term_date) or "暂无",
        almanac = {
            yi = (day_meta_almanac and day_meta_almanac.yi) or "暂无",
            ji = (day_meta_almanac and day_meta_almanac.ji) or "暂无",
        },
        countdown = build_countdown(countdown_config, now_day),
        timeline = timeline,
        future = future,
        selected = selected,
        selected_date = selected_date,
        selected_label = selected_label,
        month_cells = month_cells,
        cards = agent_cards(source, epoch_now),
    }
end

return M
