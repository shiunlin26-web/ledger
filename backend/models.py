import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # 【關卡 5】最後登入時間。用 Alembic 遷移新增的欄位（0002），不用刪表重建
    # 舊資料沒有這個值，所以要允許 None（資料庫裡是 NULL）
    last_login_at: datetime | None = None


class RefreshToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # 【關卡 1】DB 只存雜湊，不存原始 token（原本欄位叫 token）
    token_hash: str = Field(unique=True, index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # 【關卡 1】用過（換過新 token）就設成 True。
    # 不直接刪掉，是為了之後有人拿舊 token 來時，能認出「這是用過的」→ 偵測被盜用
    revoked: bool = Field(default=False)
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutboxEvent(SQLModel, table=True):
    """【關卡 24】待送出的事件（transactional outbox，說明見 outbox.py）

    和業務資料寫在同一個交易裡；worker 撿 published_at IS NULL 的送出去，送完填上時間。
    id 用 uuid 不用流水號：事件會被送到別的系統，那邊要能用這個 id 判斷「同一筆是不是已經處理過」（冪等）
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topic: str = Field(index=True)
    # JSON 欄位：payload 的欄位隨 topic 不同，不另外開表
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # worker 的查詢條件是 published_at IS NULL，要有索引，不然表大了每次輪詢都全表掃描（關卡 18）
    published_at: datetime | None = Field(default=None, index=True)


class ProcessedEvent(SQLModel, table=True):
    """【關卡 24】消費端處理過的事件 id（冪等用，說明見 outbox.py 的 handle_event）

    主鍵就是事件 id：同一筆事件第二次 INSERT 會撞主鍵，這就是「處理過了」的判斷。
    真實世界這張表在消費端自己的資料庫裡；這裡共用同一個資料庫是為了簡單。
    """

    id: uuid.UUID = Field(primary_key=True)
    topic: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
