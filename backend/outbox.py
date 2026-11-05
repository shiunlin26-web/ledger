"""【關卡 24】Transactional outbox：「註冊成功要通知別人」這件事，先寫進資料庫，再由 worker 送出去

問題：註冊成功後要寄歡迎信、更新統計、通知其他服務……如果在請求裡直接做：
  - 寄信的服務掛了，使用者就註冊失敗？不合理，使用者只是想註冊
  - 先 commit 再送：送到一半程式當掉，事件就丟了；先送再 commit：commit 失敗但信已經寄了
解法：把「待送的事件」和使用者**寫進同一個交易**（enqueue）。交易成功，事件一定在；交易失敗，事件一定不在。
之後由 worker（publish_pending / run_worker）把還沒送的事件撿出來送出去，送完標記 published_at。
這就是 transactional outbox pattern，是「資料庫和訊息系統要一致」的標準解法。

送去哪？看 KAFKA_BOOTSTRAP_SERVERS：有設就送 Kafka（本機 compose 用 Redpanda，Kafka 相容），沒設就印到 log。
Kafka 是什麼：一條一條「主題」（topic）的日誌，生產者往後面寫、消費者各自記錄讀到哪（offset）。
和 HTTP 呼叫的差別：寫的人不用等讀的人、讀的人掛了訊息還在、一筆訊息可以給好幾個系統各讀一次。

語意是 at-least-once（至少一次）：送出去之後、標記 published_at 之前程式當掉，下次會再送一次。
所以收的那邊（handle_event / run_consumer）要冪等：同一筆事件收到兩次，只處理一次。
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings
from database import engine
from models import OutboxEvent, ProcessedEvent

logger = logging.getLogger("app.outbox")

# 【關卡 24-C】同一個程序裡的「叫醒鈴」：註冊 commit 之後按一下，inline 模式的 worker 立刻醒來送，不用等下一次輪詢。
# 分開跑的 worker（compose、k8s）聽不到這個鈴，它們靠輪詢；所以輪詢間隔在那邊設短、在 Render 設長
# 鈴由 run_worker 在自己的 event loop 裡建（asyncio 的 Event 會綁定第一次用它的 loop，測試每個測試一個 loop）；
# worker 沒在跑時是 None，按鈴就是 no-op
_wakeup: asyncio.Event | None = None


def wake_worker() -> None:
    """有新事件 commit 之後呼叫。一定要在 commit 之後：worker 醒來是去查資料庫，還沒 commit 它看不到"""
    if _wakeup is not None:
        _wakeup.set()


# 這個範本只有一種事件；要加別的事件就多一個 topic 常數，consumer 的訂閱清單一起加
TOPIC_USER_REGISTERED = "user.registered"
TOPICS = [TOPIC_USER_REGISTERED]


# ---------- 生產端：請求裡 enqueue，worker 送出 ----------


def enqueue(session: AsyncSession, topic: str, payload: dict[str, Any]) -> OutboxEvent:
    """把一筆事件加進目前的 session，**不 commit**：和呼叫端的其他寫入一起進同一個交易

    payload 只放 id 和必要欄位，不放密碼雜湊之類的敏感資料：事件之後會被送到別的系統。
    """
    event = OutboxEvent(topic=topic, payload=payload)
    session.add(event)
    return event


def serialize(event: OutboxEvent) -> bytes:
    """送出去的格式：JSON，帶事件 id 讓消費端做冪等"""
    return json.dumps(
        {
            "id": str(event.id),
            "topic": event.topic,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
    ).encode()


class Publisher(Protocol):
    """送出事件的管道。測試用假的，正式用 Kafka，沒 Kafka 用 log"""

    async def send(self, topic: str, key: str, value: bytes) -> None: ...

    async def stop(self) -> None: ...


class LogPublisher:
    """沒有 Kafka 時用：事件只印到 log。線上免費方案（關卡 24-C）就是這個"""

    async def send(self, topic: str, key: str, value: bytes) -> None:
        logger.info("published", extra={"event_id": key, "topic": topic, "transport": "log"})

    async def stop(self) -> None:
        pass


class KafkaPublisher:
    """送到 Kafka（或 Redpanda）。key 用事件 id：同一個 key 一定進同一個 partition，順序才有保證"""

    def __init__(self, bootstrap_servers: str) -> None:
        # acks="all"：所有副本都寫到才算成功，寧可慢也不要丟
        self._producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers, acks="all")

    async def start(self) -> None:
        await self._producer.start()

    async def send(self, topic: str, key: str, value: bytes) -> None:
        await self._producer.send_and_wait(topic, value=value, key=key.encode())
        logger.info("published", extra={"event_id": key, "topic": topic, "transport": "kafka"})

    async def stop(self) -> None:
        await self._producer.stop()


async def make_publisher() -> Publisher:
    if settings.kafka_bootstrap_servers:
        publisher = KafkaPublisher(settings.kafka_bootstrap_servers)
        await publisher.start()
        logger.info(
            "outbox worker：送到 Kafka", extra={"brokers": settings.kafka_bootstrap_servers}
        )
        return publisher
    logger.info("outbox worker：沒設 KAFKA_BOOTSTRAP_SERVERS，事件只印到 log")
    return LogPublisher()


async def publish_pending(session: AsyncSession, publisher: Publisher, limit: int = 100) -> int:
    """撿還沒送的事件送出去，送一筆標一筆，最後一起 commit。回傳送了幾筆。

    FOR UPDATE SKIP LOCKED：好幾個 worker 同時跑時，各拿各的、不等對方，同一筆不會被送兩次（關卡 18 的鎖）。
    """
    result = await session.exec(
        select(OutboxEvent)
        .where(col(OutboxEvent.published_at).is_(None))
        .order_by(col(OutboxEvent.created_at))
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    events = result.all()
    for event in events:
        await publisher.send(event.topic, str(event.id), serialize(event))
        event.published_at = datetime.now(timezone.utc)
        session.add(event)
    await session.commit()
    return len(events)


async def run_worker(db_engine: AsyncEngine = engine) -> None:
    """一直跑：每隔 OUTBOX_POLL_SECONDS 撿一次。worker.py 單獨跑它，關卡 24-C 在 web 程序裡當背景 task 跑它

    db_engine 參數是給測試用的（測試資料庫）；平常用 database.py 的 engine。
    """
    global _wakeup
    wakeup = asyncio.Event()
    _wakeup = wakeup
    publisher = await make_publisher()
    try:
        while True:
            # 先把鈴放下再去查：查的期間若有人註冊，鈴會再被按下，下面的等待就立刻醒
            wakeup.clear()
            async with AsyncSession(db_engine) as session:
                sent = await publish_pending(session, publisher)
            if sent:
                continue  # 可能還有，馬上再撿
            # 沒事做：等鈴響，最多等 OUTBOX_POLL_SECONDS。
            # Render 上設 600 秒：worker 不會每 5 秒碰資料庫，Neon 閒置 5 分鐘才能休眠，免費方案的計算時數才省得下來；
            # 有人註冊會按鈴，不用等 10 分鐘
            try:
                await asyncio.wait_for(wakeup.wait(), timeout=settings.outbox_poll_seconds)
            except asyncio.TimeoutError:
                pass
    finally:
        _wakeup = None
        await publisher.stop()


# ---------- 消費端：收到事件做事，同一筆只做一次 ----------


async def handle_event(
    session: AsyncSession, event_id: uuid.UUID, topic: str, payload: dict[str, Any]
) -> bool:
    """處理一筆事件；同一個 id 第二次來回 False（冪等）。

    做法：ProcessedEvent 的主鍵就是事件 id，先 INSERT，撞到主鍵就是處理過了，整個交易回滾。
    「用資料庫的唯一性做冪等」和註冊的 email unique 索引是同一招（關卡 13）。
    """
    session.add(ProcessedEvent(id=event_id, topic=topic))
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        logger.info("duplicate", extra={"event_id": str(event_id), "topic": topic})
        return False
    # 這裡就是「真正要做的事」：寄歡迎信、更新統計……這個範本只記一行 log。
    # 要做的事和上面的 INSERT 在同一個交易裡（或本身冪等），才不會「標記了卻沒做」
    logger.info(
        "consumed", extra={"event_id": str(event_id), "topic": topic, "email": payload.get("email")}
    )
    await session.commit()
    return True


async def run_consumer() -> None:
    """consumer.py 跑它：訂閱 topic，一筆一筆交給 handle_event，處理完才 commit offset"""
    if not settings.kafka_bootstrap_servers:
        raise RuntimeError("consumer 需要 KAFKA_BOOTSTRAP_SERVERS")
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="jwt-auth-demo",  # 同一個 group 的消費者分攤 partition；換個 group 就能從頭再讀一次
        enable_auto_commit=False,  # 處理完才 commit offset：處理到一半當掉，重啟會再收到同一筆 → 靠 handle_event 的冪等擋
        auto_offset_reset="earliest",  # 第一次啟動從最早的開始讀，晚於生產者啟動也不會漏
    )
    await consumer.start()
    logger.info("outbox consumer：開始讀", extra={"topics": TOPICS})
    try:
        async for message in consumer:
            if (
                message.value is None
            ):  # 空訊息（Kafka 的 tombstone，compaction 用），這個專案不會產生，跳過
                await consumer.commit()
                continue
            data = json.loads(message.value)
            async with AsyncSession(engine) as session:
                await handle_event(session, uuid.UUID(data["id"]), data["topic"], data["payload"])
            await consumer.commit()
    finally:
        await consumer.stop()
