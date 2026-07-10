"""认证 API"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.api.auth import authenticate_user, create_access_token, get_current_user
from src.config.settings import Config

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: LoginRequest):
    if not authenticate_user(req.username, req.password):
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token(req.username)
    return {"access_token": token, "token_type": "bearer", "username": req.username}


@router.get("/me")
async def me(user: str = Depends(get_current_user)):
    return {"username": user, "auth_enabled": Config.ENABLE_AUTH}


@router.get("/status")
async def auth_status():
    return {
        "enabled": Config.ENABLE_AUTH,
        "demo_users": ["admin", "demo"] if Config.ENABLE_AUTH else [],
    }
