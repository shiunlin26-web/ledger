"""【關卡 22】追蹤（tracing）：一個請求從進來到回去，中間走了哪幾站、每站花多久

log（關卡 11）告訴你「這個請求 120 毫秒、回 200」；指標（metrics.py）告訴你「這小時 p95 是 80 毫秒」；
都答不了「這 120 毫秒花在哪」。追蹤把一個請求拆成一棵樹：最外層是 HTTP 請求（span），
底下是它做的每一次 SQL 查詢（子 span），每個都有開始、結束、屬性。看一眼就知道是哪一句 SQL 慢。

用的是 OpenTelemetry（OTel）：廠商中立的標準。程式只負責產生 span、用 OTLP 協定送出去；
收的那頭可以是本機 compose 裡的 collector（infra/otel/collector.yaml，只印到 log）、Grafana Cloud、
Jaeger、Datadog……換廠商不用改程式，只改環境變數。這就是為什麼不直接用某家的 SDK。

開關：沒設 OTEL_EXPORTER_OTLP_ENDPOINT 就完全不啟用（線上 Render 預設沒設，行為和以前一樣）。
設了就：
  1. 每個 HTTP 請求一個 span（FastAPIInstrumentor），span 名稱是「GET /api/me」這種路由樣板
  2. 每次 SQL 一個子 span（AsyncPGInstrumentor：asyncpg 是 SQLAlchemy 底下真的和 Postgres 講話的驅動；
     OTel 的 SQLAlchemy 套件目前只支援到 2.0，掛在驅動這一層反而更貼近實際送出的 SQL）
  3. span 帶回應的 X-Request-ID，log 也帶 trace_id（main.py 的 log middleware）：log ↔ trace 兩邊互相找得到
  4. span 先攢在記憶體，每幾秒一批用 HTTP 送到 OTLP 端點（BatchSpanProcessor），不會拖慢請求
/api/ping 和 /metrics 不追蹤：平台的 health check 每幾秒打一次，追了只是噪音。
"""

import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from config import settings

logger = logging.getLogger("app")

SERVICE = "jwt-auth-demo-backend"


def setup_tracing(app: FastAPI, exporter: SpanExporter | None = None) -> TracerProvider | None:
    """main.py 建好 app 之後呼叫一次。沒設端點就什麼都不做（回 None）。

    exporter 參數是給測試用的：測試傳一個記憶體裡的 exporter，就能檢查產生了哪些 span，不用真的送出去。
    """
    if exporter is None:
        if not settings.otel_exporter_otlp_endpoint:
            return None
        # 端點、header 這些都由 SDK 自己讀 OTEL_* 環境變數（OTEL_EXPORTER_OTLP_ENDPOINT 後面會自動接 /v1/traces），
        # 所以換成 Grafana Cloud 只要改環境變數，程式一行不改
        exporter = OTLPSpanExporter()

    # resource：這些 span 是「誰」產生的。收的那頭用 service.name 分服務、service.version 分版本
    provider = TracerProvider(
        resource=Resource.create(
            {SERVICE_NAME: SERVICE, SERVICE_VERSION: settings.app_version or "dev"}
        )
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        # 逗號分隔的正規表示式，對到的 URL 不追蹤
        excluded_urls="metrics,api/ping",
        # 把回應的 X-Request-ID 放進 span 的屬性（http.response.header.x_request_id），拿 request id 就能找到 trace
        http_capture_headers_server_response=["x-request-id"],
    )
    # 掛在 asyncpg 驅動上（全域，一個程序掛一次）：span 名稱是 SQL 的第一個字（SELECT、INSERT），db.statement 是整句
    AsyncPGInstrumentor().instrument(tracer_provider=provider)
    logger.info(
        "OpenTelemetry 追蹤已啟用", extra={"endpoint": settings.otel_exporter_otlp_endpoint}
    )
    return provider


def current_trace_id() -> str | None:
    """目前這個請求的 trace id（32 個十六進位字）；沒在追蹤就是 None。log middleware 用它把 log 和 trace 串起來"""
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None
