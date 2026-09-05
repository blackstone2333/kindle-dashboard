local json = require("json")
local lfs = require("libs/libkoreader-lfs")
local Cache = {}

function Cache.ensure(path)
    if lfs.attributes(path, "mode") == "directory" then return true end
    return lfs.mkdir(path)
end

function Cache.read(path)
    local file = io.open(path, "rb")
    if not file then return nil end
    local size = file:seek("end")
    if not size or size > 4 * 1024 * 1024 then file:close(); return nil end
    file:seek("set", 0)
    local body = file:read("*a")
    file:close()
    local ok, value = pcall(json.decode, body)
    if ok and type(value) == "table" then return value end
end

function Cache.write(path, value)
    local ok, body = pcall(json.encode, value)
    if not ok then return nil end
    local file = io.open(path .. ".tmp", "wb")
    if not file then return nil end
    local written = file:write(body)
    file:close()
    if not written then os.remove(path .. ".tmp"); return nil end
    return os.rename(path .. ".tmp", path)
end

function Cache.valid(snapshot)
    return type(snapshot) == "table" and snapshot.schema_version == 1
        and type(snapshot.events) == "table" and type(snapshot.tasks) == "table"
        and type(snapshot.generated_at) == "number"
end

return Cache
