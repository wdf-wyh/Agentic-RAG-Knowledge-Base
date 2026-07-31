"""OIDC claim mapping tests."""
from src.services.oidc_service import map_oidc_claims


def test_map_oidc_claims_admin_role():
    user = map_oidc_claims(
        {
            "sub": "oidc-1",
            "preferred_username": "alice",
            "tenant_id": "tenant-a",
            "roles": ["Administrator"],
        }
    )
    assert user.username == "alice"
    assert user.user_id == "oidc-1"
    assert user.tenant_id == "tenant-a"
    assert "admin" in user.roles
    assert user.auth_type == "oidc"


def test_map_oidc_claims_default_user_role():
    user = map_oidc_claims(
        {
            "sub": "oidc-2",
            "email": "bob@example.com",
            "roles": "viewer",
        }
    )
    assert user.username == "bob@example.com"
    assert user.roles == ["user"]
    assert user.tenant_id == "default"


def test_map_oidc_claims_auditor_role():
    user = map_oidc_claims(
        {
            "sub": "oidc-3",
            "preferred_username": "carol",
            "roles": ["Auditor"],
        }
    )
    assert "auditor" in user.roles
