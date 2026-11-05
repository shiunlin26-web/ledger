from fastapi import APIRouter, Depends

from dependencies import get_current_user
from models import User
from schemas import UserRead

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
