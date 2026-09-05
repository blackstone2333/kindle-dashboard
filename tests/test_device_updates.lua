local U = dofile(arg[1] or "device/koreader/plugins/kindleagentdashboard.koplugin/updates.lua")
local function clone(t)
    if type(t) ~= "table" then return t end
    local c={} for k,v in pairs(t) do c[k]=clone(v) end return c
end
local data={clock="10:00",date_label="日期",lunar="农历",month_label="月份",month_cells={{day=1}},
    solar_term="节气",next_solar_term="下个",almanac={yi={"a","b","c"},ji={"d"}},
    timeline={{title="安排",time="10:00",kind="日程",meta={calendar="日历"}}},future={}}
for i=1,12 do data.future[i]={title="日程"..i,time="09:00",date="09月07日 一",kind="日程"} end
local snap={generated_at=10,sources={calendar={ok=true,updated_at=10}},
    weather={temperature=20.1,low=15,high=25,uv=2,updated_at=10}}
local footer={wifi=true,battery_icon="battery-full"}
local baseline=U.capture(data,snap,0,0,footer)
local function check(name,d,s,p,f,expected)
    local actual=table.concat(U.changed(baseline,U.capture(d,s,0,p,f)),",")
    assert(actual==expected,name..": "..actual.." ~= "..expected)
    print("PASS",name)
end
local d=clone(data);d.clock="10:01"
check("minute tick changes only clock",d,snap,0,footer,"clock")
local s=clone(snap);s.generated_at=20;s.sources.calendar.updated_at=20;s.weather.updated_at=20
check("sync timestamps do not repaint",data,s,0,footer,"")
s.weather.temperature=20.4
check("same rounded weather does not repaint",data,s,0,footer,"")
s.weather.temperature=21.2
check("weather changes only weather region",data,s,0,footer,"weather")
check("right pagination changes only right list",data,snap,1,footer,"future")
d=clone(data);d.future[9].title="offscreen edit"
check("offscreen changes do not repaint",d,snap,0,footer,"")
d=clone(data);d.timeline[1].title="edit"
check("visible event edit changes timeline",d,snap,0,footer,"timeline")
local f=clone(footer);f.wifi=false
check("wifi changes only footer",data,snap,0,f,"footer")

local M = dofile(arg[2] or "device/koreader/plugins/kindleagentdashboard.koplugin/model.lua")
local now = 1788588000
local today=M.build({events={},tasks={}},now)
local next_month=M.build({events={},tasks={}},now,1)
assert(today.month_label=="2026年9月" and next_month.month_label=="2026年10月")
assert(today.clock==next_month.clock and today.date_label==next_month.date_label)
local changes=U.changed(U.capture(today,{},0,0,footer),U.capture(next_month,{},0,0,footer))
assert(table.concat(changes,",")=="calendar")
print("PASS","month navigation changes only calendar; clock and today remain real")
local january=M.build({events={},tasks={}},now,4)
assert(january.month_label=="2027年1月" and january.month_cells[1].date=="2026-12-28")
print("PASS","month navigation crosses year with Monday-first grid")
local back=M.build({events={},tasks={}},now,0)
assert(#U.changed(U.capture(today,{},0,0,footer),U.capture(back,{},0,0,footer))==0)
print("PASS","return to current month")
local selected = clone(data); selected.selected_date = "2026-09-07"; selected.selected_label = "09月07日"; selected.selected = selected.future
local selected_view = U.capture(selected,snap,0,0,footer)
local selected_changes = U.changed(baseline,selected_view)
local selected_change_text = table.concat(selected_changes,",")
assert(selected_change_text:find("calendar") and selected_change_text:find("future"))
print("PASS","selected date changes calendar frame and day schedule")
selected.selected = {selected.future[1], selected.future[2]}
local selected_one_page = U.capture(selected,snap,0,1,footer)
assert(selected_one_page.future.pages==1 and #selected_one_page.future.rows==0)
print("PASS","selected-day pagination is clamped to its own item count")
