import logging
import math
import os
import pathlib
import time
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

logger = logging.getLogger("rate_limiter")

REDIS_URL = "redis://localhost:6379/0"
LIMIT = int(os.getenv("RATE_LIMIT", 1000000))  # requests per minute
WINDOW_MS = int(os.getenv("RATE_WINDOW_MS", 60_000))  # window size in milliseconds
EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json"}

SCRIPT_PATH = pathlib.Path(__file__).parent.parent / "scripts" / "sliding_window.lua"


@asynccontextmanager
async def lifespan(app: FastAPI):
    #--startup 
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    
    app.state.rate_limit_script = app.state.redis.register_script(
        SCRIPT_PATH.read_text()
    )
    print(f"Connected to Redis | limit={LIMIT} per {WINDOW_MS}ms")
    yield 
    #shutdown 
    await app.state.redis.aclose() 
    
app = FastAPI(title="Distributed Rate Limiter", lifespan=lifespan)

def get_identity(request: Request) -> str:
    user_id = request.headers.get("x-user-id")
    if user_id:
        return f"user:{user_id}"
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)
    

    key = f"rl:{get_identity(request)}"
    
    start = time.perf_counter() 
    try:
        allowed, remaining, retry_after_ms = await request.app.state.rate_limit_script(
            keys=[key],
            args=[WINDOW_MS, LIMIT, uuid.uuid4().hex],
        )
    except RedisError:
        logger.exception("Rate limiter unavailable, failing open")
        return await call_next(request)
    check_ms = (time.perf_counter() - start) * 1000 
    
    headers = {
        "X-RateLimit-Limit": str(LIMIT),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Check-Ms": f"{check_ms:.2f}",
    }
    
    if not allowed:
        headers["Retry-After"] = str(max(1, math.ceil(retry_after_ms / 1000)))
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers=headers,
        )

    response = await call_next(request)
    response.headers.update(headers)
    return response


@app.get("/api/data")
async def get_data():
    return {"message": "Here is your protected data"}