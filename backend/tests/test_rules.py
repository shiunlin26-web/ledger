"""【關卡 4】單元測試：直接測試函式，不需要資料庫、不需要 API

測試的基本格式（Arrange-Act-Assert）：
1. 準備資料
2. 執行要測的東西
3. 用 assert 檢查結果；assert 後面是 False 時測試就失敗
"""

import jwt
import pytest
from pydantic import ValidationError

from config import settings
from schemas import UserCreate, UserLogin, check_password_chars
from security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)

# ---------- 關卡 0：密碼規則 ----------


def test_英數符號密碼可以通過():
    assert check_password_chars("P@ss w0rd!~") == "P@ss w0rd!~"


# @pytest.mark.parametrize：同一個測試用不同資料跑好幾次，每組資料算一個測試
@pytest.mark.parametrize("password", ["中文密碼中文密碼", "abcdefgh😀", "tab\tinside"])
def test_非ASCII或控制字元會被拒絕(password):
    # pytest.raises：預期這段程式「會丟出」這個錯誤，沒丟出來測試反而失敗
    with pytest.raises(ValueError):
        check_password_chars(password)


@pytest.mark.parametrize(
    "password, ok",
    [
        ("a" * 7, False),  # 太短
        ("a" * 8, True),  # 剛好最短
        ("a" * 72, True),  # 剛好最長
        ("a" * 73, False),  # 太長
    ],
)
def test_註冊密碼長度限制(password, ok):
    if ok:
        UserCreate(email="a@b.com", password=password)  # 不丟錯就是通過
    else:
        with pytest.raises(ValidationError):
            UserCreate(email="a@b.com", password=password)


def test_登入不套用密碼規則():
    # 短密碼、中文密碼在登入時都能通過「格式檢查」，對不對交給 verify_password
    UserLogin(email="a@b.com", password="x")
    UserLogin(email="a@b.com", password="中文")


# 【關卡 13】hash_password / verify_password 改成 async（bcrypt 丟到執行緒池），測試也要 await
async def test_超過72bytes的密碼驗證時直接回False而不是丟錯():
    hashed = await hash_password("password123")
    assert await verify_password("密" * 30, hashed) is False  # 90 bytes


async def test_密碼雜湊與驗證():
    hashed = await hash_password("password123")
    assert hashed != "password123"  # 存的不是明文
    assert await verify_password("password123", hashed) is True
    assert await verify_password("wrong-pass", hashed) is False


# ---------- 關卡 1：refresh token 雜湊 ----------


def test_hash_token_同樣輸入得到同樣結果():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("abc")) == 64  # SHA-256 的十六進位字串固定 64 字元


# ---------- 關卡 13：access token 一定要有 exp 和 sub ----------


def test_access_token可以簽發並解開():
    token = create_access_token(42)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert "exp" in payload and "iat" in payload


@pytest.mark.parametrize("payload", [{"sub": "1"}, {"exp": 4102444800}])
def test_缺少exp或sub的token會被拒絕(payload):
    # 用同一把密鑰、正確簽章，但故意少一個欄位：簽章對也不能過
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
