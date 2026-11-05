import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import settings

# 【關卡 1】這個檔案保護三樣東西，各用一種工具，不要混：
# - 密碼        → bcrypt：慢（成本 12 = 揉 4096 遍 ≈ 0.1 秒）+ 每次隨機撒鹽。存起來比對用。
#                 密碼是人想的、字典猜得到，所以要慢（小偷猜一次也要 0.1 秒）、要鹽（同一個密碼
#                 在不同人那裡結果不同，事先算好的表沒用）。登入是「先用 email 找到人，再比對」，
#                 所以不需要拿雜湊當 key，每次結果不同沒關係。
# - refresh token → SHA-256：快、同樣輸入永遠同樣輸出。存起來當查表的 key。
#                 票是 32 個隨機 byte，猜不到，不需要慢；而且收到 cookie 要靠雜湊 WHERE 出那一列，
#                 必須固定，bcrypt 每次不同查不到。
# - access token  → HMAC 簽章（JWT）：不存資料庫。內容誰都看得懂（不是加密），但改一個字簽章就
#                 對不上；只有拿 JWT_SECRET 的後端算得出正確簽章。驗的時候重算簽章比對 + 看 exp。

# 【關卡 13】bcrypt 刻意很慢（一次約 50～300 毫秒），而且是純 CPU 運算。
# 直接在 async 函式裡呼叫，整個 event loop 會被卡住：那幾百毫秒內後端不能處理任何其他請求，
# 包含 /api/ping。十個人同時登入，第十個人要等前面九個算完。
# 解法：丟到執行緒池（asyncio.to_thread），event loop 繼續服務別人，算完再回來。
# 這是 async 後端最常見的效能錯誤之一：「async 不等於快，擋住 loop 的東西都要丟出去」。


def _hash_password_sync(password: str) -> str:
    # gensalt() 預設成本 12，每次呼叫重擲一把鹽。輸出固定格式 60 字：
    #   $2b$12$ + 22 字的鹽 + 31 字的結果
    # 鹽不是祕密，就寫在前面；checkpw 會自己從這串讀出鹽、重算、比對後 31 字。
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password_sync(plain: str, hashed: str) -> bool:
    plain_bytes = plain.encode()
    # 【關卡 0】bcrypt 遇到超過 72 bytes 會直接丟錯（→ 500）。
    # 註冊時已經擋掉這種密碼，所以超過的一定是錯的密碼，直接回傳 False
    if len(plain_bytes) > 72:
        return False
    return bcrypt.checkpw(plain_bytes, hashed.encode())


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_password_sync, password)


async def verify_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(_verify_password_sync, plain, hashed)


# 【關卡 13】登入時「帳號不存在」也要做一次 bcrypt 比對，用這個假的雜湊值。
# 不然「帳號不存在」會在 1 毫秒內回 401，「密碼錯」要花 100 毫秒以上，
# 攻擊者量一下回應時間就能列舉出哪些 email 有註冊（timing attack / user enumeration）。
DUMMY_PASSWORD_HASH = _hash_password_sync(secrets.token_urlsafe(16))


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,  # 【關卡 13】簽發時間。除錯和之後要做「某時間點前的 token 全部作廢」會用到
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    # 【關卡 13】require：沒有 exp 或 sub 的 token 直接拒絕。
    # PyJWT 預設「有 exp 才檢查過期」，一個被竄改成沒有 exp 的 token 會永遠有效
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )


def create_refresh_token() -> str:
    """產生一個隨機的 refresh token 字串"""
    return secrets.token_urlsafe(32)


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


def hash_token(token: str) -> str:
    """【關卡 1】refresh token 存進 DB 前先做 SHA-256 雜湊。
    DB 外洩時，攻擊者只拿到雜湊值，無法反推出原本的 token 拿去用。
    （token 本身是 32 bytes 隨機字串，猜不到，所以用快速的 SHA-256 就夠，不需要 bcrypt）
    """
    return hashlib.sha256(token.encode()).hexdigest()
