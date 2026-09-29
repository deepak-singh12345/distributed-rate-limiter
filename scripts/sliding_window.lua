local key       = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit     = tonumber(ARGV[2])
local req_id    = ARGV[3]

-- Redis is the single clock (fixes gateway clock skew)
local t = redis.call("TIME")
local now_ms = t[1] * 1000 + math.floor(t[2]/1000)

-- 1. Prune entries that fell out of the window
redis.call("ZREMRANGEBYSCORE", key, 0, now_ms - window_ms)

-- 2. Count what's left 
local count = redis.call("ZCARD", key)

if count < limit then 
    -- 3a Allowed. Member = timestamp + unique id, so same-ms requests don't collapse
    redis.call("ZADD", key, now_ms, now_ms .. "-" .. req_id)
    redis.call("PEXPIRE", key, window_ms)
    return {1, limit - count -1, 0}
else
    -- 3b Rejected. The oldest entry decides when a slot frees up 
    local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
    local retry_after = tonumber(oldest[2] + window_ms - now_ms)
    return {0, 0, retry_after}
end 