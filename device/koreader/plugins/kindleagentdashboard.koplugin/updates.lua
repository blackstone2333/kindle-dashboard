-- Compare only what is visible, not sync timestamps or off-screen records.
local Updates = {}
Updates.order = {"clock", "date", "weather", "timeline", "calendar", "almanac", "future", "footer"}
Updates.regions = {
    clock={40,20,390,130}, date={50,155,390,90}, weather={440,40,300,205},
    timeline={50,310,690,635}, calendar={792,36,612,465},
    almanac={792,512,615,79}, future={792,608,615,397}, footer={1276,1018,110,36},
}

local function equal(a,b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key,value in pairs(a) do if not equal(value,b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end

local function rounded(value)
    return type(value) == "number" and math.floor(value+0.5) or "--"
end

local function rows(items, page, size)
    local result = {}
    for i=page*size+1, math.min(#items,(page+1)*size) do
        local item = items[i]
        local m = type(item.meta) == "table" and item.meta or {}
        result[#result+1] = {title=item.title,time=item.time,kind=item.kind,date=item.date,
            calendar=m.calendar,location=m.location,list=m.list}
    end
    return result
end

local function firstTwo(value)
    if type(value) ~= "table" then return value end
    return {value[1],value[2]}
end

function Updates.capture(data,snapshot,page,future_page,footer)
    local weather = type(snapshot.weather) == "table" and snapshot.weather or {}
    local uv = type(weather.uv) == "number" and (weather.uv < 3 and "低" or weather.uv < 6 and "中" or "高") or "--"
    local almanac = data.almanac or {}
    local calendar_ok = ((snapshot.sources or {}).calendar or {}).ok
    local display = data.selected_date and data.selected or data.future
    return {
        clock=data.clock, date={data.date_label,data.lunar},
        weather={location=weather.location,icon=weather.icon,condition=weather.condition,
            temperature=rounded(weather.temperature),low=rounded(weather.low),high=rounded(weather.high),
            rain=rounded(weather.rain_probability),wind=rounded(weather.wind_level),uv=uv},
        timeline={rows=rows(data.timeline,page,6),page=page,pages=math.max(1,math.ceil(#data.timeline/6)),
            empty_ok=#data.timeline==0 and calendar_ok or false},
        calendar={data.month_label,data.month_cells,selected_date=data.selected_date},
        almanac={data.solar_term,data.next_solar_term,firstTwo(almanac.yi),firstTwo(almanac.ji)},
        future={selected_date=data.selected_date,selected_label=data.selected_label,
            rows=rows(display,future_page,5),page=future_page,pages=math.max(1,math.ceil(#display/5))},
        footer={wifi=footer.wifi,battery_icon=footer.battery_icon},
    }
end

function Updates.changed(before,after)
    local changed = {}
    for _,name in ipairs(Updates.order) do
        if not before or not equal(before[name],after[name]) then changed[#changed+1]=name end
    end
    return changed
end

return Updates
