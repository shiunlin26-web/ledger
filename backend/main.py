import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings
from database import engine, get_session
from logging_config import setup_logging
from metrics import setup_metrics
from outbox import run_worker
from rate_limit import get_client_ip, limiter
from routes import auth, users
from tracing import current_trace_id, setup_tracing

# 【關卡 11】log 設定要在最前面做，之後所有 logger 都會用同一個格式
setup_logging(level=settings.log_level, json_output=settings.log_json)
logger = logging.getLogger("app")

# 【關卡 11】Sentry：錯誤追蹤服務。程式丟出沒接住的例外時，它會把 traceback、請求資訊、
# 發生次數整理好寄給你，比翻 log 快很多。沒設定 SENTRY_DSN 就完全不啟用（本機通常不設）。
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        # 區分是哪個環境出錯。Render 會自動注入 RENDER=true 這個環境變數
        environment="production" if settings.app_version else "development",
        release=settings.app_version,
        # 不要把使用者的 IP、cookie、authorization header 送去 Sentry（隱私）
        send_default_pii=False,
        # 效能追蹤先關掉，免費額度留給錯誤
        traces_sample_rate=0.0,
    )
    logger.info("Sentry 已啟用")


# 【關卡 5】原本這裡的 lifespan 在啟動時用 SQLModel.metadata.create_all 自動建表。
# create_all 只會建「不存在的表」，改欄位時不會更新已存在的表（關卡 1 就踩過）。
# 現在資料表結構改由 Alembic 管理：改完 models.py 後執行
#   alembic revision --autogenerate --rev-id 000X -m "說明"   ← 產生遷移檔
#   alembic upgrade head                                     ← 套用到資料庫
#
# 【關卡 13】lifespan 回來了，但只做一件事：關機時把連線池的連線好好關掉。
# 沒有這段，部署換版（平台送 SIGTERM）時連線會被硬切，資料庫端留下一堆「對方消失」的連線，
# 免費方案的連線數上限很小，累積幾次就連不上。yield 之前是啟動、之後是關機。
#
# 【關卡 24-C】OUTBOX_WORKER=inline 時，啟動時在同一個程序裡開一個背景 task 跑 outbox worker（outbox.py 的 run_worker）。
# 正式做法是獨立的 worker 服務（compose 的 worker、k8s 另一個 Deployment），但 Render 免費方案只能有一個 web service，
# 所以線上用這個模式：事件照樣從 outbox 撿出來、印到 log（沒有 Kafka）。多個副本同時跑也沒關係，SKIP LOCKED 會各撿各的。
# 關機時先取消這個 task、等它把 publisher 關好，再關連線池。
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker_task: asyncio.Task[None] | None = None
    if settings.outbox_worker == "inline":
        worker_task = asyncio.create_task(run_worker(), name="outbox-worker")
        logger.info("outbox worker 在 web 程序裡當背景 task 跑")
    yield
    if worker_task is not None:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


# 【關卡 17】頻率限制：slowapi 要從 app.state 找到 limiter；超過上限時用我們自己的 429 回應
app.state.limiter = limiter


def rate_limit_exceeded(request: Request, exc: Exception) -> Response:
    # slowapi 內建的 handler 回 {"error": ...}，前端的 getErrorMessage 讀的是 detail，所以自己寫一個。
    # exc.detail 長得像 "10 per 1 minute"
    assert isinstance(exc, RateLimitExceeded)
    response = JSONResponse(
        status_code=429,
        content={"detail": f"請求太頻繁，請稍後再試（上限 {exc.detail}）"},
    )
    # 補上 Retry-After 等標頭（和內建 handler 做法相同）
    return limiter._inject_headers(response, request.state.view_rate_limit)


app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,  # 【關卡 2】改從設定讀
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 【關卡 11】每個請求記一行 log，並且給它一個 request id
#
# middleware = 每個請求進來、回應出去都會經過的一層。這裡做三件事：
# 1. 產生 request_id，放進回應的 X-Request-ID header。使用者回報「我剛剛出錯了」時，
#    請他把這個 id 給你，你就能在 log 裡找到那一筆，不用大海撈針
# 2. 記錄方法、路徑、狀態碼、耗時。這就是「結構化 log」：每個欄位分開，可以搜尋、統計
# 3. 沒被接住的例外（500）在這裡記下 traceback 再往外丟，確保 log 裡一定有東西，
#    不會出現「500 但 log 什麼都沒有」（DEBUGGING.md 裡最難查的那種）
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        raise
    response.headers["X-Request-ID"] = request_id
    # 【關卡 19】API 的回應一律不准快取。瀏覽器、Vercel 的 CDN、公司的 proxy 都可能把 GET 的回應存起來，
    # /api/me 被存起來就會把 A 的資料給 B（同一台共用電腦、同一個 proxy 後面）。
    # no-store 是「連存都不要存」，比 no-cache（存了但每次要問）更嚴。登入相關的 API 一律 no-store 是業界慣例
    response.headers.setdefault("Cache-Control", "no-store")
    extra = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
    }
    # 【關卡 22】有在追蹤時把 trace_id 也記進 log：從 log 的一行能找到 trace，從 trace 的 request id 能找到 log
    trace_id = current_trace_id()
    if trace_id:
        extra["trace_id"] = trace_id
    logger.info("request", extra=extra)
    return response


# 【關卡 22】指標：每個請求累計到 http_requests_total 與 http_request_duration_seconds，/metrics 給 Prometheus 抓（metrics.py）
setup_metrics(app)
# 【關卡 22】追蹤：設了 OTEL_EXPORTER_OTLP_ENDPOINT 才啟用，每個請求一個 span、每句 SQL 一個子 span（tracing.py）
setup_tracing(app)


# 【關卡 10】所有 API 統一掛在 /api 底下：/api/auth/login、/api/me、/api/ping
#
# 為什麼？正式環境前端在 Vercel、後端在 Render，是兩個不同的網域。
# 如果前端直接打後端網址，就是「跨站」請求，refresh token 的 cookie（SameSite=Lax）不會被帶上，
# 重新整理就會掉登入；改成 SameSite=None 又會被 iPhone Safari 擋掉。
#
# 解法是讓瀏覽器以為前後端是同一個網站：前端只打「自己網域的 /api/...」，
# 由 Vercel 把 /api/* 轉發（rewrite）到 Render。這就是「反向代理」。
# 本機開發也一樣：Vite 的 server.proxy 把 /api/* 轉到 localhost:8000（frontend/vite.config.ts）。
# 後端把所有路徑都加上 /api 前綴，代理時就不用改寫路徑，本機和正式環境長得一模一樣。
api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(users.router)


@api.get("/ping")
async def ping():
    """【關卡 11】liveness：「程式活著嗎」。不碰資料庫，永遠很快。Render 的 health check 打這個"""
    return {"message": "pong"}


@api.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    """【關卡 11】readiness：「能正常服務嗎」。會真的查一次資料庫，給人和監控工具看。

    回傳：
    - status：ok / degraded
    - db：ok / error（連得到資料庫嗎）
    - migration：目前資料庫的 alembic 版本（確認遷移有沒有跑到最新）
    - version：目前跑的 commit（確認線上是不是你剛推的那版）

    為什麼 Render 的 health check 不用這個？因為資料庫短暫斷線時，liveness 還是 ok（程式沒壞），
    用 readiness 會讓平台以為程式壞了而不斷重啟，反而更糟。兩個分開是業界慣例。
    """
    db_status = "ok"
    migration = None
    # 【關卡 13】原始 SQL 不走 session.exec（它是給 select(Model) 用的，型別上不接受 text()），
    # 也不走 session.execute（SQLModel 會發棄用警告），直接拿底層的連線來跑
    try:
        conn = await session.connection()
        await conn.execute(text("SELECT 1"))
        try:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            migration = result.scalar_one_or_none()
        except Exception:
            # 測試環境用 create_all 建表，沒有 alembic_version 這張表，不算錯
            await session.rollback()
            migration = "unknown"
    except Exception:
        logger.exception("health check: database unreachable")
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "migration": migration,
        "version": settings.app_version,
    }


@api.get("/_boom", include_in_schema=False)
async def boom():
    """【關卡 11】演練用：故意丟一個沒接住的例外，看 log 和 Sentry 有沒有收到。

    平常關著（ENABLE_DEBUG_ENDPOINTS 預設 false，回 404），不然任何人都能幫你灌爆 Sentry 額度。
    要演練時到 Render 的 Environment 暫時設成 true。
    """
    if not settings.enable_debug_endpoints:
        raise HTTPException(status_code=404, detail="Not Found")
    raise RuntimeError("演練：這是故意丟出來的錯誤")


@api.get("/_ip", include_in_schema=False)
async def whoami(request: Request):
    """【關卡 17】除錯用：看 X-Forwarded-For 長什麼樣、頻率限制會把你算成哪個 IP。

    用來決定 TRUSTED_PROXY_HOPS 要設幾：從前端網址打一次、直接打 Render 網址再打一次，比較兩者。
    和 /_boom 一樣預設關閉。
    """
    if not settings.enable_debug_endpoints:
        raise HTTPException(status_code=404, detail="Not Found")
    return {
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
        "client_host": request.client.host if request.client else None,
        "trusted_proxy_hops": settings.trusted_proxy_hops,
        "rate_limit_key": get_client_ip(request),
    }


app.include_router(api)
