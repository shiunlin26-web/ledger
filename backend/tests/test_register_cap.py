"""【關卡 24-C】示範站的帳號數上限：到了註冊回 503，沒設就不限制"""

from helpers import register

from config import settings


async def test_沒設上限就不限制(client):
    assert settings.max_users is None
    assert (await register(client, "a@test.com", "Passw0rd!x")).status_code == 201
    assert (await register(client, "b@test.com", "Passw0rd!x")).status_code == 201


async def test_帳號數到上限就回503(client, monkeypatch):
    monkeypatch.setattr(settings, "max_users", 1)
    assert (await register(client, "a@test.com", "Passw0rd!x")).status_code == 201
    r = await register(client, "b@test.com", "Passw0rd!x")
    assert r.status_code == 503
    assert "額滿" in r.json()["detail"]
