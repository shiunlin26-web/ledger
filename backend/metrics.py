"""【關卡 22】指標（metrics）：把「多少請求、多快、多少錯」累計成數字，讓 Prometheus 定期來抓

關卡 11 的 log 是「一筆一筆的事件」：哪個請求、幾毫秒、回什麼。要回答「這一小時平均多快」「錯誤率多少」，
得把幾萬行 log 加總。指標反過來：程式自己累計，Prometheus 每幾秒來讀一次 /metrics，存成時間序列，
Grafana 再畫成圖。三種訊號各有用途：log 找單一請求、指標看趨勢與告警、追蹤（關卡 22-B）看一個請求走了哪幾站。

這裡用 prometheus_client 手寫，不用現成的 instrumentator 套件：二十行就夠，而且每一步都看得到。

    http_requests_total{method, route, status}     計數器（只增不減）：請求數
    http_request_duration_seconds{method, route}   直方圖：耗時落在哪個區間，Grafana 用它算 p95
    app_info{version}                              固定是 1，label 帶 commit，儀表板上看現在跑哪一版

route 用「路由樣板」（/api/auth/login），不用實際路徑：路徑裡若有 id（/todos/123）每個 id 都會變成一條時間序列，
Prometheus 會被撐爆（這叫 cardinality 爆炸）。沒對上任何路由的（亂打的 404）一律記成 unmatched，同樣是為了不讓人灌爆它。

開關：METRICS_ENABLED 預設 false，/metrics 回 404。/metrics 刻意不放在 /api 底下：Vercel 只轉發 /api/*，
所以就算線上打開，外面也打不到；compose 裡的 Prometheus 直接連 backend:8000/metrics（infra/compose.yaml）。
"""

import time

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.routing import Route

from config import settings

REQUESTS = Counter("http_requests_total", "HTTP 請求數", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "HTTP 請求耗時（秒）", ["method", "route"])
APP_INFO = Gauge("app_info", "目前跑的版本（值固定是 1，看 label）", ["version"])


def _route_template(request: Request) -> str:
    # 路由對上之後，Starlette 的 Router 會把 Route 物件放進 scope["route"]；沒對上（404）就沒有這個 key
    route = request.scope.get("route")
    if isinstance(route, Route):
        return route.path
    return "unmatched"


def setup_metrics(app: FastAPI) -> None:
    """掛上計數的 middleware 和 /metrics 端點。main.py 建好 app 之後呼叫一次"""
    APP_INFO.labels(version=settings.app_version or "dev").set(1)

    @app.middleware("http")
    async def record_metrics(request: Request, call_next):
        # 抓指標的請求本身不算進去，不然 Prometheus 每 5 秒就幫你加一筆
        if request.url.path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        status = (
            "500"  # 沒接住的例外：main.py 的 log middleware 會記 traceback，這裡只需要知道它是 500
        )
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            route = _route_template(request)
            REQUESTS.labels(request.method, route, status).inc()
            DURATION.labels(request.method, route).observe(time.perf_counter() - start)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        if not settings.metrics_enabled:
            raise HTTPException(status_code=404, detail="Not Found")
        # Prometheus 的文字格式：一行一個數字，瀏覽器直接開就看得懂
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
