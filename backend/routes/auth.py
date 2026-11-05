from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings
from database import get_session
from dependencies import get_current_user
from models import RefreshToken, User
from outbox import enqueue, wake_worker
from rate_limit import limiter
from schemas import ChangePasswordRequest, Token, UserCreate, UserLogin, UserRead
from security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    refresh_token_expiry,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def set_refresh_cookie(response: Response, token: str) -> None:
    """【關卡 1】login 和 refresh 都要設 cookie，抽成共用函式"""
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,  # JS 讀不到
        samesite="lax",  # 防 CSRF
        secure=settings.cookie_secure,  # 【關卡 2】改從設定讀：本機 http 用 False，正式環境 True
        max_age=settings.refresh_token_expire_days * 24 * 3600,  # 天數換算成秒
        path="/api/auth",  # 只在 /api/auth/* 路徑帶上（【關卡 10】API 全部搬到 /api 底下）
    )


async def issue_refresh_token(session: AsyncSession, user_id: int) -> str:
    """【關卡 1】產生新的 refresh token，DB 存雜湊，回傳原始字串（要放進 cookie）"""
    token = create_refresh_token()
    session.add(
        RefreshToken(
            token_hash=hash_token(token),
            user_id=user_id,
            expires_at=refresh_token_expiry(),
        )
    )
    return token


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: int) -> None:
    """【關卡 3】刪掉某個使用者的所有 refresh token = 所有裝置都要重新登入
    （重複使用偵測、登出所有裝置、改密碼都會用到，所以抽成共用函式）
    注意：只有排進待辦，呼叫的人要自己 commit
    """
    # 【關卡 13】col()：告訴型別檢查器「這是資料表的欄位，不是普通的 int」，
    # 否則 pyright 會把 RefreshToken.user_id == user_id 當成普通的 bool 比較而報錯。執行結果完全一樣
    await session.exec(delete(RefreshToken).where(col(RefreshToken.user_id) == user_id))


async def delete_expired_refresh_tokens(session: AsyncSession, user_id: int) -> None:
    """【關卡 3】清掉某個使用者已過期的 refresh token
    過期的 token 不管有沒有 revoked 都不能用了，留著只是佔空間
    """
    await session.exec(
        delete(RefreshToken).where(
            col(RefreshToken.user_id) == user_id,
            col(RefreshToken.expires_at) < datetime.now(timezone.utc),
        )
    )


# 【關卡 17】註冊也限制：不然可以用腳本灌一堆假帳號。
# slowapi 規定被限制的端點要有 request 參數；要回 X-RateLimit-* 標頭還要有 response 參數（它把標頭塞進去）
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.auth_rate_limit)
async def register(
    request: Request,
    response: Response,
    data: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    # 檢查 email 是否已存在（給使用者看得懂的錯誤）
    result = await session.exec(select(User).where(User.email == data.email))
    existing = result.first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # 【關卡 24-C】示範站的保險：帳號數到上限就不收（503）。先查再寫有空窗，多收幾筆無所謂，不值得為此加鎖
    if settings.max_users is not None:
        total = (await session.exec(select(func.count()).select_from(User))).one()
        if total >= settings.max_users:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="註冊已額滿（這是示範站）",
            )

    # 建立新用戶
    user = User(
        email=data.email,
        hashed_password=await hash_password(data.password),
    )
    session.add(user)
    try:
        # flush：先把 INSERT 送到資料庫拿到 user.id，但還不 commit；email 重複的 IntegrityError 也在這裡發生
        await session.flush()
        # 【關卡 24】「有人註冊了」這個事件和使用者寫進同一個交易（outbox.py）：
        # commit 成功兩個都在，失敗兩個都不在。寄信、統計之類的事交給 worker，不在這個請求裡做
        enqueue(session, "user.registered", {"user_id": user.id, "email": user.email})
        await session.commit()
    except IntegrityError:
        # 【關卡 13】競態（race condition）：上面查過「不存在」，但在 commit 前另一個請求剛好註冊了同一個 email。
        # 「先查再寫」永遠有這個空窗，真正守住唯一性的是資料庫的 unique 索引（models.py）。
        # 它丟出 IntegrityError 時要接住回 400，不然會變成 500
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        ) from None
    await session.refresh(user)
    # 【關卡 24-C】commit 之後叫醒同一個程序裡的 worker（inline 模式），事件幾秒內就送出，不用等下一次輪詢
    wake_worker()
    return user


# 【關卡 17】同一個 IP 每分鐘最多 10 次：擋暴力破解。第 11 次回 429，前端會顯示「請求太頻繁」
@router.post("/login", response_model=Token)
@limiter.limit(settings.auth_rate_limit)
async def login(
    request: Request,
    data: UserLogin,  # 【關卡 0】登入改用 UserLogin，不套用註冊的密碼規則
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    # 查用戶
    result = await session.exec(select(User).where(User.email == data.email))
    user = result.first()
    # 【關卡 13】帳號不存在也要做一次 bcrypt 比對（對著假的雜湊），讓兩種失敗花的時間一樣，
    # 不然從回應時間就能猜出哪些 email 有註冊（security.py 的 DUMMY_PASSWORD_HASH 有說明）
    hashed = user.hashed_password if user else DUMMY_PASSWORD_HASH
    password_ok = await verify_password(data.password, hashed)
    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    # 【關卡 13】User.id 的型別是 int | None（新物件還沒存進 DB 時是 None），
    # 從 DB 查出來的一定有值。assert 告訴型別檢查器這件事，也在不該發生時立刻炸出來
    assert user.id is not None
    user_id = user.id

    # 簽 access token
    access_token = create_access_token(user_id)

    # 【關卡 5】記錄最後登入時間（下面 commit 時一起寫入）
    user.last_login_at = datetime.now(timezone.utc)

    # 【關卡 3】順便清掉這個使用者過期的 refresh token，避免資料表一直變大
    await delete_expired_refresh_tokens(session, user_id)

    # 產生並儲存 refresh token
    refresh_token = await issue_refresh_token(session, user_id)
    await session.commit()

    set_refresh_cookie(response, refresh_token)
    return Token(access_token=access_token)


@router.post("/refresh", response_model=Token)
async def refresh(
    response: Response,  # 【關卡 1】新增：要用它設定新的 cookie
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    # 查 DB：先雜湊再比對
    # with_for_update() 會把這一列鎖住直到 commit，
    # 同一個 token 同時來兩個請求時，第二個會等第一個做完才讀，不會兩個都換成功
    result = await session.exec(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_token))
        .with_for_update()
    )
    rt = result.first()

    if not rt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # 【關卡 1】重複使用偵測：這個 token 已經換過了，卻又被拿來用
    # → 可能被偷了（正常使用者手上只會有最新的那個）
    # → 把這個使用者所有 refresh token 全刪掉，所有裝置都要重新登入
    if rt.revoked:
        await revoke_all_refresh_tokens(session, rt.user_id)
        await session.commit()  # 一定要在 raise 前 commit，raise 之後的程式碼不會執行
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reused",
        )

    # 檢查過期
    if rt.expires_at < datetime.now(timezone.utc):
        await session.delete(rt)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # ⚠️ 先把 user_id 存到變數：commit() 之後 rt 的屬性會「過期」，
    # 再讀 rt.user_id 會觸發重新查 DB，在 async 裡會丟 MissingGreenlet 錯誤（500）
    user_id = rt.user_id

    # 【關卡 1】輪替：舊的作廢、發一個新的
    rt.revoked = True
    new_refresh_token = await issue_refresh_token(session, user_id)
    await session.commit()

    set_refresh_cookie(response, new_refresh_token)

    # 簽新的 access token
    access_token = create_access_token(user_id)
    return Token(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    # 刪掉 DB 裡的 refresh token（一樣先雜湊再查）
    if refresh_token:
        result = await session.exec(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
        )
        rt = result.first()
        if rt:
            await session.delete(rt)
            await session.commit()

    # 清掉 cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",  # 刪 cookie 時 path 要和設定時一樣，否則瀏覽器會當成另一個 cookie、刪不掉
    )

    return None


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),  # 需要帶 access token 才能呼叫
    session: AsyncSession = Depends(get_session),
):
    """【關卡 3】登出所有裝置：刪掉這個使用者的所有 refresh token

    ⚠️ 其他裝置手上的 access token 在過期前（最多 JWT_EXPIRE_MINUTES 分鐘）還是能用，
    因為驗證 access token 不查 DB。等它過期、要 refresh 時才會失敗被登出。
    """
    assert current_user.id is not None
    await revoke_all_refresh_tokens(session, current_user.id)
    await session.commit()

    # 這台裝置的 cookie 也清掉
    response.delete_cookie(key="refresh_token", path="/api/auth")
    return None


@router.post("/change-password", response_model=Token)
async def change_password(
    data: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """【關卡 3】改密碼：成功後其他裝置全部登出，目前這台保持登入"""
    # 1. 確認目前密碼正確
    #    用 400 而不是 401：401 代表「沒登入 / token 失效」，
    #    前端 apiFetch 看到 401 會以為 token 過期而去 refresh，這裡不是那種情況
    if not await verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前密碼錯誤",
        )

    # 2. 新密碼不能跟舊的一樣
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密碼不能和目前密碼相同",
        )

    # commit 之後 current_user 的屬性會過期（關卡 1 的坑），先存起來
    assert current_user.id is not None
    user_id = current_user.id

    # 3. 更新密碼
    current_user.hashed_password = await hash_password(data.new_password)

    # 4. 撤銷所有 refresh token → 其他裝置之後 refresh 會失敗、被登出
    #    （密碼可能就是因為外洩才改的，舊的登入狀態都不該再信任）
    await revoke_all_refresh_tokens(session, user_id)

    # 5. 幫目前這台裝置發新的 refresh token，讓使用者不用重新登入
    new_refresh_token = await issue_refresh_token(session, user_id)
    await session.commit()

    set_refresh_cookie(response, new_refresh_token)
    return Token(access_token=create_access_token(user_id))
