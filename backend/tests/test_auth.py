"""【關卡 4】整合測試：透過 API 測試完整流程（會用到測試資料庫）

這些測試把關卡 0～3 手動驗證過的情境，全部寫成程式。
以後改任何程式，跑一次 pytest 就知道有沒有把之前的功能改壞。
"""

import asyncio
from datetime import datetime, timedelta, timezone

from conftest import test_engine
from helpers import EMAIL, PASSWORD, auth_header, login, register
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import RefreshToken


async def count_refresh_tokens() -> int:
    """直接查測試資料庫：現在有幾筆 refresh token"""
    async with AsyncSession(test_engine) as session:
        result = await session.exec(select(RefreshToken))
        return len(result.all())


# ---------- 註冊 ----------


async def test_註冊成功(client):
    res = await register(client)

    assert res.status_code == 201
    body = res.json()
    assert body["email"] == EMAIL
    assert "hashed_password" not in body  # 回應裡不能有密碼雜湊


async def test_重複註冊回400(client):
    await register(client)
    res = await register(client)
    assert res.status_code == 400


async def test_中文密碼註冊回422(client):
    res = await register(client, password="中文密碼中文密碼")
    assert res.status_code == 422


# ---------- 登入 ----------


async def test_登入成功拿到access_token和refresh_cookie(client):
    await register(client)
    res = await login(client)

    assert res.status_code == 200
    assert "access_token" in res.json()
    assert client.cookies.get("refresh_token")  # client 會像瀏覽器一樣存下 cookie
    assert await count_refresh_tokens() == 1


async def test_密碼錯誤回401(client):
    await register(client)
    res = await login(client, password="wrong-password")
    assert res.status_code == 401


async def test_登入時密碼太短也回401而不是422(client):
    # 關卡 0：登入不套用密碼規則，不洩漏規則給攻擊者
    await register(client)
    res = await login(client, password="short")
    assert res.status_code == 401


# ---------- /me ----------


async def test_帶access_token可以取得自己的資料(client):
    await register(client)
    token = (await login(client)).json()["access_token"]

    res = await client.get("/api/me", headers=auth_header(token))

    assert res.status_code == 200
    assert res.json()["email"] == EMAIL


async def test_登入後會記錄最後登入時間(client):
    # 關卡 5：用 Alembic 新增的 last_login_at 欄位
    await register(client)
    token = (await login(client)).json()["access_token"]

    res = await client.get("/api/me", headers=auth_header(token))

    assert res.json()["last_login_at"] is not None


async def test_沒帶access_token回401(client):
    res = await client.get("/api/me")
    assert res.status_code == 401


# ---------- 關卡 1：refresh token 輪替與重複使用偵測 ----------


async def test_refresh會換發新的refresh_token(client):
    await register(client)
    await login(client)
    old_cookie = client.cookies.get("refresh_token")

    res = await client.post("/api/auth/refresh")

    assert res.status_code == 200
    assert "access_token" in res.json()
    assert client.cookies.get("refresh_token") != old_cookie  # cookie 換新了


async def test_舊的refresh_token再被使用會撤銷全部(client, make_client):
    await register(client)
    await login(client)
    old_cookie = client.cookies.get("refresh_token")
    await client.post("/api/auth/refresh")  # old_cookie 被作廢，client 拿到新的

    # 模擬「小偷」：另一個 client 拿著偷來的舊 cookie
    thief = make_client(cookies={"refresh_token": old_cookie})
    res = await thief.post("/api/auth/refresh")

    assert res.status_code == 401
    assert res.json()["detail"] == "Refresh token reused"
    assert await count_refresh_tokens() == 0  # 全部被刪掉

    # 真正的使用者也被登出了
    res = await client.post("/api/auth/refresh")
    assert res.status_code == 401


async def test_同一個token同時refresh只有一個成功(client, make_client):
    # 關卡 1 的 with_for_update()：同時送兩個請求，只能有一個換成功
    await register(client)
    await login(client)
    cookie = client.cookies.get("refresh_token")

    a = make_client(cookies={"refresh_token": cookie})
    b = make_client(cookies={"refresh_token": cookie})
    # asyncio.gather：同時送出兩個請求，等兩個都回來（相當於 JS 的 Promise.all）
    res_a, res_b = await asyncio.gather(a.post("/api/auth/refresh"), b.post("/api/auth/refresh"))

    assert sorted([res_a.status_code, res_b.status_code]) == [200, 401]


async def test_沒有cookie時refresh回401(client):
    res = await client.post("/api/auth/refresh")
    assert res.status_code == 401


async def test_DB只存refresh_token的雜湊(client):
    await register(client)
    await login(client)
    cookie = client.cookies.get("refresh_token")

    async with AsyncSession(test_engine) as session:
        rt = (await session.exec(select(RefreshToken))).one()

    assert rt.token_hash != cookie  # DB 裡不是原始字串


# ---------- 登出 ----------


async def test_登出後refresh失敗(client):
    await register(client)
    await login(client)

    res = await client.post("/api/auth/logout")
    assert res.status_code == 204
    assert await count_refresh_tokens() == 0

    res = await client.post("/api/auth/refresh")
    assert res.status_code == 401


async def test_登出只影響自己這台裝置(make_client):
    phone, laptop = make_client(), make_client()
    await register(phone)
    await login(phone)
    await login(laptop)

    await phone.post("/api/auth/logout")

    res = await laptop.post("/api/auth/refresh")
    assert res.status_code == 200  # 電腦不受影響


# ---------- 關卡 3：登出所有裝置 ----------


async def test_登出所有裝置(make_client):
    phone, laptop = make_client(), make_client()
    await register(phone)
    token = (await login(phone)).json()["access_token"]
    laptop_token = (await login(laptop)).json()["access_token"]
    assert await count_refresh_tokens() == 2

    res = await phone.post("/api/auth/logout-all", headers=auth_header(token))

    assert res.status_code == 204
    assert await count_refresh_tokens() == 0
    assert (await laptop.post("/api/auth/refresh")).status_code == 401

    # 關卡 3 的限制：電腦手上的 access token 在過期前還是能用
    res = await laptop.get("/api/me", headers=auth_header(laptop_token))
    assert res.status_code == 200


async def test_登出所有裝置需要access_token(client):
    res = await client.post("/api/auth/logout-all")
    assert res.status_code == 401


# ---------- 關卡 3：修改密碼 ----------


async def change_password(client, token, current, new):
    return await client.post(
        "/api/auth/change-password",
        headers=auth_header(token),
        json={"current_password": current, "new_password": new},
    )


async def test_改密碼成功(make_client):
    phone, laptop = make_client(), make_client()
    await register(phone)
    token = (await login(phone)).json()["access_token"]
    await login(laptop)

    res = await change_password(phone, token, PASSWORD, "new-password-1")

    assert res.status_code == 200
    assert "access_token" in res.json()
    assert (await phone.post("/api/auth/refresh")).status_code == 200  # 這台保持登入
    assert (await laptop.post("/api/auth/refresh")).status_code == 401  # 其他裝置被登出
    assert (await login(make_client())).status_code == 401  # 舊密碼不能用
    assert (await login(make_client(), password="new-password-1")).status_code == 200


async def test_改密碼時目前密碼錯誤回400(client):
    await register(client)
    token = (await login(client)).json()["access_token"]

    res = await change_password(client, token, "wrong-password", "new-password-1")

    # 400 而不是 401：避免前端誤以為 token 過期
    assert res.status_code == 400


async def test_新舊密碼相同回400(client):
    await register(client)
    token = (await login(client)).json()["access_token"]
    res = await change_password(client, token, PASSWORD, PASSWORD)
    assert res.status_code == 400


async def test_新密碼不符合規則回422(client):
    await register(client)
    token = (await login(client)).json()["access_token"]
    res = await change_password(client, token, PASSWORD, "中文密碼中文密碼")
    assert res.status_code == 422


# ---------- 關卡 3：登入時清理過期 token ----------


async def test_登入時會清掉過期的refresh_token(client):
    await register(client)
    await login(client)

    # 直接在 DB 塞一筆已經過期的 token
    async with AsyncSession(test_engine) as session:
        session.add(
            RefreshToken(
                token_hash="expired",
                user_id=1,
                revoked=True,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        await session.commit()
    assert await count_refresh_tokens() == 2

    await login(client)

    # 過期那筆被清掉，剩下：第一次登入的 1 筆 + 這次登入的 1 筆
    assert await count_refresh_tokens() == 2
    async with AsyncSession(test_engine) as session:
        expired = (
            await session.exec(select(RefreshToken).where(RefreshToken.token_hash == "expired"))
        ).first()
    assert expired is None


async def test_request_log會記下是誰的請求(client, caplog):
    # 【關卡 20】只看 path 次數分不出是誰在換票；登入、換票、帶 access token 的請求要記 user_id
    await register(client)
    caplog.clear()
    res = await login(client)
    access_token = res.json()["access_token"]
    await client.post("/api/auth/refresh")
    me = await client.get("/api/me", headers=auth_header(access_token))
    await client.get("/api/ping")

    # middleware 用 extra= 加的欄位會掛在 LogRecord 上，從 __dict__ 拿
    logged = {r.__dict__["path"]: r.__dict__ for r in caplog.records if r.getMessage() == "request"}
    user_id = me.json()["id"]
    assert logged["/api/auth/login"]["user_id"] == user_id
    assert logged["/api/auth/refresh"]["user_id"] == user_id
    assert logged["/api/me"]["user_id"] == user_id
    assert "user_id" not in logged["/api/ping"]  # 不知道是誰就不記


async def test_email不分大小寫(client):
    # 【關卡 20】EmailStr 只把網域轉小寫；Test@ 和 test@ 以前會是兩個帳號，用別的大小寫也登不進去
    res = await register(client, email="Mixed.Case@Example.COM")
    assert res.status_code == 201
    assert res.json()["email"] == "mixed.case@example.com"  # 存進去的是小寫

    res = await register(client, email="mixed.case@example.com")
    assert res.status_code == 400  # 同一個人，不能再註冊一次

    res = await login(client, email="MIXED.CASE@example.com")
    assert res.status_code == 200  # 用哪種大小寫都登得進去
