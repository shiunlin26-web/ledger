"""【關卡 22】指標：預設關閉、打開後數字會動、路由樣板與 unmatched"""

from config import settings


async def test_metrics預設關閉(client):
    r = await client.get("/metrics")
    assert r.status_code == 404


async def test_打開後每個請求都會被計數(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", True)
    before = await client.get("/metrics")
    assert before.status_code == 200
    assert before.headers["content-type"].startswith("text/plain")

    await client.get("/api/ping")
    await client.get("/no-such-path")  # 404：沒對上任何路由

    body = (await client.get("/metrics")).text
    # 計數器：label 順序是宣告時的 method、route、status；route 是路由樣板
    assert 'http_requests_total{method="GET",route="/api/ping",status="200"}' in body
    # 亂打的路徑一律記成 unmatched，不會每個路徑長出一條時間序列
    assert 'http_requests_total{method="GET",route="unmatched",status="404"}' in body
    # 直方圖：_count 是觀測次數，_bucket 是各區間的累計
    assert 'http_request_duration_seconds_count{method="GET",route="/api/ping"}' in body
    assert "http_request_duration_seconds_bucket{" in body
    # 版本：測試環境沒設 APP_VERSION，就是 dev
    assert 'app_info{version="dev"} 1.0' in body


async def test_抓metrics本身不算進請求數(client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_enabled", True)
    for _ in range(3):
        await client.get("/metrics")
    body = (await client.get("/metrics")).text
    assert 'route="/metrics"' not in body
