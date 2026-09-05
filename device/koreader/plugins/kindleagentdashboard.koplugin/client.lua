local ffiutil = require("ffi/util")
local json = require("json")
local Client = {}

function Client.new(root, plugin_path)
    return setmetatable({ root = root, cache = dofile(plugin_path .. "/cache.lua") }, { __index = Client })
end

function Client:start()
    if self.pid then return false end
    local config = self.cache.read(self.root .. "/config.json") or {}
    if type(config.url) ~= "string" or not config.url:match("^https?://")
        or type(config.token) ~= "string" or config.token == "" then
        self.error = "尚未配置同步服务"; return false
    end
    self.started = os.time()
    os.remove(self.root .. "/request-result.json")
    local pid = ffiutil.runInSubProcess(function()
        local ok, err = pcall(function()
            local http = config.url:match("^https://") and require("ssl.https") or require("socket.http")
            http.TIMEOUT = 12
            local chunks, length = {}, 0
            local _, code = http.request{
                url = config.url:gsub("/$", "") .. "/api/v1/snapshot",
                method = "GET", redirect = false,
                headers = { Authorization = "Bearer " .. config.token, Accept = "application/json" },
                sink = function(chunk)
                    if chunk then
                        length = length + #chunk
                        if length > 4 * 1024 * 1024 then return nil, "response too large" end
                        chunks[#chunks + 1] = chunk
                    end
                    return 1
                end,
            }
            if tonumber(code) ~= 200 then error("同步连接失败 (" .. tostring(code or "network") .. ")") end
            local decoded = json.decode(table.concat(chunks))
            if not self.cache.valid(decoded) then error("同步数据格式无效") end
            assert(self.cache.write(self.root .. "/snapshot.json", decoded), "缓存写入失败")
        end)
        self.cache.write(self.root .. "/request-result.json", {
            ok = ok, at = os.time(), error = ok and "" or "同步失败，继续显示缓存",
        })
    end)
    if not pid then self.error = "无法启动同步任务"; return false end
    self.pid = pid
    return true
end

function Client:poll()
    if not self.pid then return nil end
    if os.time() - self.started > 25 then self:stop(); self.error = "同步超时，继续显示缓存"; return false end
    if not ffiutil.isSubProcessDone(self.pid) then return nil end
    self.pid = nil
    local result = self.cache.read(self.root .. "/request-result.json") or {}
    if not result.ok then self.error = result.error or "同步未完成"; return false end
    local snapshot = self.cache.read(self.root .. "/snapshot.json")
    if not self.cache.valid(snapshot) then self.error = "缓存数据无效"; return false end
    self.error = nil
    self.last_success = result.at
    return snapshot
end

function Client:stop()
    if self.pid then
        ffiutil.terminateSubProcess(self.pid)
        ffiutil.isSubProcessDone(self.pid, true)
        self.pid = nil
    end
end

return Client
