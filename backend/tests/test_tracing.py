"""【關卡 22】追蹤：沒設端點就不啟用；設了就每個請求一個 span、SQL 一個子 span、帶 request id"""

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text

from config import settings
from database import engine
from tracing import current_trace_id, setup_tracing


async def test_沒設端點就不啟用(client):
    assert settings.otel_exporter_otlp_endpoint is None
    assert setup_tracing(FastAPI()) is None
    # 沒在追蹤時 trace id 是 None，log 裡就不會出現 trace_id 欄位
    assert current_trace_id() is None


async def test_每個請求一個span_SQL一個子span():
    # 用一個小 app 測，不動 main.py 的 app（instrumentation 只能掛一次，而且其他測試不該被影響）
    exporter = InMemorySpanExporter()
    app = FastAPI()

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Request-ID"] = "req-123"
        return response

    @app.get("/hello")
    async def hello():
        trace_id = current_trace_id()  # 在請求裡，span 已經開著
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"trace_id": trace_id}

    provider = setup_tracing(app, exporter=exporter)
    assert provider is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        body = (await c.get("/hello")).json()
    provider.force_flush()

    spans = {s.name: s for s in exporter.get_finished_spans()}
    # HTTP 的 span：名稱是路由樣板，帶回應的 X-Request-ID
    http_span = spans["GET /hello"]
    assert http_span.attributes is not None
    assert http_span.attributes["http.route"] == "/hello"
    assert http_span.attributes["http.response.header.x_request_id"] == ("req-123",)
    assert http_span.context is not None
    # 請求裡拿到的 trace id 就是這個 span 的 trace id
    assert body["trace_id"] == format(http_span.context.trace_id, "032x")
    # SQL 的子 span（asyncpg 層）：名稱是 SQL 的第一個字，同一個 trace，parent 是 HTTP 的 span
    sql_spans = [s for s in spans.values() if s.name == "SELECT"]
    assert sql_spans, f"沒有 SQL 的 span，只有：{sorted(spans)}"
    sql_span = sql_spans[0]
    assert sql_span.context is not None and sql_span.parent is not None
    assert sql_span.context.trace_id == http_span.context.trace_id
    assert sql_span.attributes is not None
    assert sql_span.attributes["db.statement"] == "SELECT 1"
    # resource：收的那頭靠這個分服務
    assert http_span.resource.attributes["service.name"] == "jwt-auth-demo-backend"
