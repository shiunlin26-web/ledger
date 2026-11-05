"""【關卡 5】Alembic 執行遷移時的進入點

執行 alembic upgrade / revision 等指令時，Alembic 會執行這個檔案：
1. 連上資料庫（用 .env 的 DATABASE_URL）
2. 拿 models.py 的資料表定義（target_metadata）和資料庫現況做比對或套用遷移

這個檔案是 `alembic init -t async` 產生的範本，改了兩個地方：
- 連線字串改從 config.py 讀
- target_metadata 指向 SQLModel 的資料表定義
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

import models  # noqa: F401  載入 User、RefreshToken，SQLModel.metadata 才會有它們
from config import settings

config = context.config

# 套用 alembic.ini 裡的 log 設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 【改 1】「資料表應該長怎樣」的定義來源：models.py 裡所有 table=True 的 class
# alembic revision --autogenerate 會拿它和資料庫現況比對，自動產生遷移檔
target_metadata = SQLModel.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # 【改 2】連線字串從 config.py 讀，跟後端用同一個 DATABASE_URL
    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


asyncio.run(run_async_migrations())
