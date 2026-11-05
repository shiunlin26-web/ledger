import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings

# 【關卡 10】Neon 的 pooled 連線字串（主機名稱含 "-pooler"）背後是 PgBouncer，
# 它不支援 asyncpg 預設的 prepared statement 快取，要關掉，否則會隨機出現
# "prepared statement ... already exists" 的錯誤。用直連字串就不需要。
connect_args = {"statement_cache_size": 0} if "-pooler" in settings.database_url else {}

# 【關卡 10】pool_pre_ping=True：從連線池拿連線出來用之前，先發一個很便宜的查詢確認它還活著。
# Neon 免費方案閒置 5 分鐘會休眠，休眠前建立的連線都會死掉；沒有這個設定，
# 休眠後的第一個請求會拿到死連線，直接 500（connection is closed）。
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)

# 【關卡 2】DB_ECHO=true 時把每一句 SQL 印出來（學習用）。
# 【關卡 18】不用 create_async_engine(echo=True)：它會自己再掛一個輸出，每句 SQL 印兩次、格式還不一樣。
# 改成把 sqlalchemy.engine 這個 logger 的等級調到 INFO，它就走關卡 11 統一的 log 格式，只印一次
if settings.db_echo:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


# 【關卡 13】回傳型別寫清楚：這是一個「會 yield AsyncSession 的 async generator」。
# FastAPI 的 Depends 看得懂 yield（結束時自動關 session），型別檢查器也需要這個標註才不會報錯
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session
