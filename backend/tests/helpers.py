"""【關卡 4】測試共用的小工具與測試資料"""

from httpx import AsyncClient

EMAIL = "test@example.com"
PASSWORD = "password123"


async def register(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD):
    return await client.post("/api/auth/register", json={"email": email, "password": password})


async def login(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


def auth_header(access_token: str) -> dict:
    """產生 Authorization header：{"Authorization": "Bearer xxx"}"""
    return {"Authorization": f"Bearer {access_token}"}
