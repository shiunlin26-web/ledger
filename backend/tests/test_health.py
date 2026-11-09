"""【關卡 11】維護相關的測試：health、request id、除錯端點預設關閉"""

from httpx import ASGITransport, AsyncClient

from config import settings
from main import app


async def test_ping不碰資料庫也能回(client):
    r = await client.get("/api/ping")
    assert r.status_code == 200
    assert r.json() == {"message": "pong"}


async def test_health會回報資料庫狀態(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    # 測試資料庫是 create_all 建的，沒有 alembic_version 表，所以是 unknown
    assert body["migration"] == "unknown"


async def test_每個回應都不准快取(client):
    # 【關卡 19】/api/me 被瀏覽器或 proxy 快取會把 A 的資料給 B，所以 API 一律 no-store
    res = await client.get("/api/ping")
    assert res.headers["cache-control"] == "no-store"


async def test_每個回應都有request_id(client):
    r = await client.get("/api/ping")
    assert r.headers.get("X-Request-ID")
    # 呼叫端自己帶 id 的話要原樣回傳（方便串接前端或其他服務的 log）
    r = await client.get("/api/ping", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


async def test_除錯端點預設關閉(client):
    r = await client.get("/api/_boom")
    assert r.status_code == 404


async def test_500也回JSON並帶request_id(monkeypatch):
    # 【關卡 20】沒接住的例外以前回純文字、沒有 X-Request-ID，使用者手上沒有 id 可以回報
    monkeypatch.setattr(settings, "enable_debug_endpoints", True)
    # raise_app_exceptions=False：讓例外變成 500 回應交回來，而不是直接在測試裡丟出
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/_boom", headers={"X-Request-ID": "boom123"})
    assert r.status_code == 500
    assert r.headers["X-Request-ID"] == "boom123"
    assert r.headers["cache-control"] == "no-store"
    assert r.json() == {"detail": "Internal Server Error"}  # 不洩漏例外內容
