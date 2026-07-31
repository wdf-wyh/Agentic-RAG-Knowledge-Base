"""OpenID Connect (OIDC) 企业 SSO 集成。"""
from __future__ import annotations

import json
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from src.config.settings import Config
from src.models.auth import UserIdentity

_oidc_states: dict[str, float] = {}
_discovery_cache: Optional[dict] = None
_discovery_cached_at: float = 0.0
_STATE_TTL_SECONDS = 600
_DISCOVERY_TTL_SECONDS = 3600


def is_oidc_enabled() -> bool:
    return (
        Config.ENABLE_OIDC
        and bool(Config.OIDC_ISSUER.strip())
        and bool(Config.OIDC_CLIENT_ID.strip())
    )


def _issuer_base() -> str:
    return Config.OIDC_ISSUER.rstrip("/")


def _fetch_discovery() -> dict:
    global _discovery_cache, _discovery_cached_at
    now = time.time()
    if _discovery_cache and now - _discovery_cached_at < _DISCOVERY_TTL_SECONDS:
        return _discovery_cache

    url = f"{_issuer_base()}/.well-known/openid-configuration"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    _discovery_cache = response.json()
    _discovery_cached_at = now
    return _discovery_cache


def create_login_state() -> str:
    state = secrets.token_urlsafe(32)
    _oidc_states[state] = time.time()
    _cleanup_states()
    return state


def verify_login_state(state: str) -> bool:
    created_at = _oidc_states.pop(state, None)
    if created_at is None:
        return False
    return time.time() - created_at <= _STATE_TTL_SECONDS


def _cleanup_states() -> None:
    cutoff = time.time() - _STATE_TTL_SECONDS
    expired = [key for key, ts in _oidc_states.items() if ts < cutoff]
    for key in expired:
        _oidc_states.pop(key, None)


def build_authorization_url(state: str) -> str:
    discovery = _fetch_discovery()
    params = {
        "client_id": Config.OIDC_CLIENT_ID,
        "response_type": "code",
        "scope": Config.OIDC_SCOPES,
        "redirect_uri": Config.OIDC_REDIRECT_URI,
        "state": state,
    }
    return f"{discovery['authorization_endpoint']}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    discovery = _fetch_discovery()
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": Config.OIDC_REDIRECT_URI,
        "client_id": Config.OIDC_CLIENT_ID,
    }
    if Config.OIDC_CLIENT_SECRET:
        payload["client_secret"] = Config.OIDC_CLIENT_SECRET

    response = requests.post(discovery["token_endpoint"], data=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def decode_id_token(id_token: str) -> dict:
    try:
        from jose import jwt
    except ImportError as exc:
        raise RuntimeError("请安装 python-jose: pip install python-jose[cryptography]") from exc

    discovery = _fetch_discovery()
    jwks_uri = discovery.get("jwks_uri")
    if not jwks_uri:
        return jwt.get_unverified_claims(id_token)

    jwks_response = requests.get(jwks_uri, timeout=15)
    jwks_response.raise_for_status()
    jwks = jwks_response.json()

    return jwt.decode(
        id_token,
        jwks,
        algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
        audience=Config.OIDC_CLIENT_ID,
        issuer=discovery.get("issuer", _issuer_base()),
        options={"verify_at_hash": False},
    )


def _normalize_roles(raw_roles: Any) -> list[str]:
    if raw_roles is None:
        return []
    if isinstance(raw_roles, str):
        if raw_roles.startswith("["):
            try:
                parsed = json.loads(raw_roles)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in raw_roles.split(",") if part.strip()]
    if isinstance(raw_roles, list):
        return [str(item) for item in raw_roles]
    return [str(raw_roles)]


def _map_app_roles(idp_roles: list[str]) -> list[str]:
    admin_roles = {role.strip().lower() for role in Config.OIDC_ADMIN_ROLES if role.strip()}
    auditor_roles = {role.strip().lower() for role in Config.OIDC_AUDITOR_ROLES if role.strip()}
    mapped: list[str] = []

    for role in idp_roles:
        normalized = role.strip().lower()
        if normalized in admin_roles:
            mapped.append("admin")
        elif normalized in auditor_roles:
            mapped.append("auditor")

    if not mapped:
        mapped.append("user")
    return sorted(set(mapped))


def map_oidc_claims(claims: dict) -> UserIdentity:
    username = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn")
        or claims.get("sub")
    )
    if not username:
        raise ValueError("OIDC token 缺少用户标识 claim")

    user_id = str(claims.get("sub") or username)
    tenant_claim = Config.OIDC_TENANT_CLAIM.strip()
    tenant_id = str(claims.get(tenant_claim) or Config.DEFAULT_TENANT_ID)
    idp_roles = _normalize_roles(claims.get(Config.OIDC_ROLE_CLAIM))

    return UserIdentity(
        username=str(username),
        user_id=user_id,
        tenant_id=tenant_id,
        roles=_map_app_roles(idp_roles),
        auth_type="oidc",
    )


def identity_from_code(code: str) -> UserIdentity:
    tokens = exchange_code_for_tokens(code)
    id_token = tokens.get("id_token")
    if not id_token:
        raise ValueError("OIDC token 响应缺少 id_token")
    claims = decode_id_token(id_token)
    return map_oidc_claims(claims)
