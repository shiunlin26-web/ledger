import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import User
from security import decode_access_token

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    # 【關卡 13】只接 PyJWT 的錯誤（簽章不對、過期、缺欄位）和 sub 不是數字的情況。
    # 以前是 except Exception：連程式本身的 bug（例如 settings 壞掉）都會被包成 401，查不到原因
    except (jwt.PyJWTError, KeyError, ValueError):
        # from None：不要把 PyJWT 的原始錯誤串在這個例外後面。
        # 對外只需要知道「token 無效」，原始錯誤的細節（簽章不對？過期？）不該洩漏給呼叫端
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
