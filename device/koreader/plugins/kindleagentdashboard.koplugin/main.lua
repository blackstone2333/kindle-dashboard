local Device = require("device")
local UIManager = require("ui/uimanager")
local WidgetContainer = require("ui/widget/container/widgetcontainer")
local PluginShare = require("pluginshare")
local logger = require("logger")

local KindleAgentDashboard = WidgetContainer:extend{
    name = "kindleagentdashboard",
    is_doc_only = false,
}

function KindleAgentDashboard:init()
    self.root = require("datastorage"):getSettingsDir() .. "/kindle-agent-dashboard"
    self.cache = dofile(self.path .. "/cache.lua")
    self.cache.ensure(self.root)
    if PluginShare.kindle_agent_owner then
        UIManager:unschedule(PluginShare.kindle_agent_owner._watch)
    end
    PluginShare.kindle_agent_owner = self
    self.ui.menu:registerToMainMenu(self)
    self._watch = function() self:watch() end
    UIManager:scheduleIn(2, self._watch)
    logger.info("KindleAgentDashboard: plugin initialized")
end

function KindleAgentDashboard:addToMainMenu(menu_items)
    menu_items.kindle_agent_dashboard = {
        text = "Kindle Agent 看板",
        sorting_hint = "more_tools",
        sub_item_table = {
            {
                text = "打开 V13 看板",
                callback = function()
                    UIManager:nextTick(function() self:open() end)
                end,
            },
        },
    }
end

function KindleAgentDashboard:open()
    if self.view and not self.view.closed then return end
    local previous = Device.screen:getRotationMode()
    if Device.screen:getWidth() < Device.screen:getHeight() then
        UIManager:broadcastEvent(require("ui/event"):new("SetRotationMode", 1))
    end
    local config = self.cache.read(self.root .. "/config.json") or {}
    local ok, view = pcall(function()
        return dofile(self.path .. "/view.lua"):new{
            root=self.root, plugin_path=self.path, owner=self, previous_rotation=previous,
            font_name=config.font_name,
        }
    end)
    if not ok then
        logger.err("KindleAgentDashboard: open failed", view)
        self.cache.write(self.root .. "/status.json", {active=false,error=tostring(view),at=os.time()})
        UIManager:show(require("ui/widget/infomessage"):new{text="看板打开失败，诊断已保存。"})
        UIManager:broadcastEvent(require("ui/event"):new("SetRotationMode", previous))
        return
    end
    self.view = view
    UIManager:show(view, "full")
end

function KindleAgentDashboard:watch()
    if PluginShare.kindle_agent_owner ~= self then return end
    UIManager:scheduleIn(2, self._watch)
    for _, action in ipairs({"open", "close", "refresh", "screenshot"}) do
        local marker = self.root .. "/" .. action .. ".request"
        local file = io.open(marker, "rb")
        if file then
            file:close(); os.remove(marker)
            if action == "open" then self:open()
            elseif action == "close" and self.view then self.view:onClose()
            elseif action == "refresh" and self.view then self.view.last_request=0; self.view:tick(true)
            elseif action == "screenshot" then Device.screen:shot(self.root .. "/screen.png") end
        end
    end
end

function KindleAgentDashboard:onExit()
    UIManager:unschedule(self._watch)
    if self.view then self.view:onClose() end
end

return KindleAgentDashboard
