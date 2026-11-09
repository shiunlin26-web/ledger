"""【關卡 4】測試的共用設定（pytest 會自動載入這個檔案）

這裡定義的 fixture，所有測試檔都能直接當參數使用，不用 import。

fixture 是什麼？「測試開始前幫你準備好的東西」。
測試函式的參數寫 client，pytest 就會先執行下面的 client() 函式，把結果傳進來。
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import models  # noqa: F401  確保資料表定義都有載入，create_all 才知道要建哪些表
from config import settings
from database import get_session
from main import app
from rate_limit import limiter

# 【關卡 17】測試預設關掉頻率限制：所有測試都從同一個 IP 打登入，不關會被自己擋。
# 要測限制本身的測試用 test_rate_limit.py 的 fixture 暫時打開
limiter.enabled = False

# ---------- 安全檢查：絕對不能拿正式資料庫來跑測試 ----------
if not settings.test_database_url:
    pytest.exit(
        "請在 backend/.env 設定 TEST_DATABASE_URL（測試專用資料庫），說明見 docs/LEARNING.md 關卡 4",
        returncode=1,
    )
if settings.test_database_url == settings.database_url:
    pytest.exit("TEST_DATABASE_URL 不能和 DATABASE_URL 相同，測試會清空資料表！", returncode=1)

# 測試專用的資料庫連線
# NullPool：每次用完就關閉連線，不重複使用。
# 因為每個測試都在自己的 event loop 跑，重複使用連線會出錯
test_engine = create_async_engine(settings.test_database_url, poolclass=NullPool)

_tables_ready = False


@pytest.fixture(autouse=True)  # autouse=True：每個測試都自動套用，不用寫在參數裡
async def clean_database():
    """每個測試開始前：確保資料表存在，並清空所有資料 → 每個測試都從乾淨的狀態開始"""
    global _tables_ready
    async with test_engine.begin() as conn:
        if not _tables_ready:
            # 第一次：砍掉重建，確保資料表結構和 models.py 一致（測試資料庫可以隨便砍）
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
            _tables_ready = True
        # TRUNCATE：清空資料；RESTART IDENTITY：id 從 1 重新算；CASCADE：連帶清掉有關聯的資料
        await conn.execute(
            text(
                'TRUNCATE TABLE processedevent, outboxevent, refreshtoken, "user" RESTART IDENTITY CASCADE'
            )
        )
    yield  # yield 之前是「測試前」要做的事，之後是「測試後」（這裡不用做什麼）


async def get_test_session():
    """取代原本的 get_session：讓 API 連到測試資料庫"""
    async with AsyncSession(test_engine) as session:
        yield session


# dependency_overrides：FastAPI 提供的測試功能
# 意思是「所有用到 Depends(get_session) 的地方，改成呼叫 get_test_session」
app.dependency_overrides[get_session] = get_test_session


@pytest.fixture
async def client():
    """一個測試用的 HTTP client，相當於「一台裝置（一個瀏覽器）」

    ASGITransport 讓請求直接送進 FastAPI app，不需要真的啟動 uvicorn。
    client 會自動保存 cookie，跟瀏覽器一樣。
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def make_client():
    """需要「好幾台裝置」時用：每呼叫一次，就產生一個有獨立 cookie 的新 client"""
    clients = []

    def _make(**kwargs) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test", **kwargs)
        clients.append(c)
        return c

    yield _make

    # yield 之後是「測試結束後」：把開過的 client 都關掉
    for c in clients:
        await c.aclose()


@pytest.fixture
async def db():
    """【關卡 24】直接看測試資料庫的內容（例如 outbox 表有沒有那一筆），和 API 走同一個資料庫"""
    async with AsyncSession(test_engine) as session:
        yield session
