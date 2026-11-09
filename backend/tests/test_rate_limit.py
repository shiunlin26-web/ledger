"""【關卡 17】頻率限制：第 11 次登入回 429；客戶端 IP 從 X-Forwarded-For 正確取出"""

import pytest
from helpers import login, register
from starlette.requests import Request

from config import settings
from rate_limit import get_client_ip, limiter


@pytest.fixture
def rate_limited():
    """conftest 預設把限制關掉；這裡暫時打開，並清空計數，測完再關回去"""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


async def test_登入超過上限回429並帶Retry_After(client, rate_limited):
    await register(client)
    # settings.auth_rate_limit 是 "10/minute"：前 10 次正常（密碼對不對都算一次），第 11 次被擋
    for _ in range(10):
        res = await login(client, password="wrong-password")
        assert res.status_code == 401
    res = await login(client)  # 密碼正確也一樣被擋：限制看的是次數，不是結果
    assert res.status_code == 429
    assert "請求太頻繁" in res.json()["detail"]
    assert "retry-after" in res.headers


async def test_註冊也有上限(client, rate_limited):
    for i in range(10):
        res = await register(client, email=f"u{i}@example.com")
        assert res.status_code == 201
    res = await register(client, email="one-too-many@example.com")
    assert res.status_code == 429


async def test_限制關閉時不會擋(client):
    # conftest 預設 limiter.enabled = False：其他測試檔連續登入幾十次都不該被擋
    await register(client)
    for _ in range(12):
        assert (await login(client)).status_code == 200


# ---------- get_client_ip：從 X-Forwarded-For 取 IP ----------


def fake_request(xff: str | None, client_host: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    scope = {"type": "http", "headers": headers, "client": (client_host, 1234)}
    return Request(scope)


@pytest.mark.parametrize(
    "hops, xff, expected",
    [
        (0, None, "10.0.0.1"),  # 本機沒代理：用連線來源
        (0, "1.1.1.1", "10.0.0.1"),  # 本機卻有人自己填標頭：不理它
        (1, "1.1.1.1", "1.1.1.1"),  # 一層代理（Render）：最右邊是代理接上去的真 IP
        (2, "1.1.1.1, 2.2.2.2", "1.1.1.1"),  # Vercel + Render：右邊數第 2 段
        (2, "9.9.9.9, 1.1.1.1, 2.2.2.2", "1.1.1.1"),  # 攻擊者在最左邊塞假 IP：照樣取右邊數第 2 段
        (2, "1.1.1.1", "10.0.0.1"),  # 段數不夠（有人直接打 Render）：退回連線來源
    ],
)
def test_從X_Forwarded_For取客戶端IP(monkeypatch, hops, xff, expected):
    monkeypatch.setattr(settings, "trusted_proxy_hops", hops)
    assert get_client_ip(fake_request(xff)) == expected
