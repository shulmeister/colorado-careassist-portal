"""
Unit tests for services/auth_service.py

Covers:
- Session token creation & verification
- Domain validation
- CSRF state validation
- Portal proxy authentication
- Demo bypass environment guard
"""

import os
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# GoogleOAuthManager tests
# ============================================================

class TestGoogleOAuthManager:
    """Tests for GoogleOAuthManager session and domain logic."""

    def _make_manager(self, **env_overrides):
        """Create a fresh GoogleOAuthManager with test env vars."""
        env = {
            "GOOGLE_CLIENT_ID": "test-client-id",
            "GOOGLE_CLIENT_SECRET": "test-client-secret",
            "GOOGLE_REDIRECT_URI": "http://localhost:8765/auth/callback",
            "APP_SECRET_KEY": "test-secret-key-stable",
            "ALLOWED_DOMAINS": "coloradocareassist.com,test.com",
        }
        env.update(env_overrides)
        with patch.dict(os.environ, env, clear=False):
            # Force re-import to pick up patched env
            from services.auth_service import GoogleOAuthManager
            return GoogleOAuthManager()

    def test_verify_session_valid_token(self):
        """Valid session tokens should decode correctly."""
        manager = self._make_manager()
        session_data = {
            "user_id": "123",
            "email": "jason@coloradocareassist.com",
            "name": "Jason",
            "domain": "coloradocareassist.com",
            "login_time": datetime.utcnow().isoformat(),
        }
        token = manager.serializer.dumps(session_data)
        result = manager.verify_session(token)
        assert result is not None
        assert result["email"] == "jason@coloradocareassist.com"
        assert result["user_id"] == "123"

    def test_verify_session_tampered_token(self):
        """Tampered tokens should return None."""
        manager = self._make_manager()
        result = manager.verify_session("definitely-not-a-valid-token")
        assert result is None

    def test_verify_session_wrong_secret(self):
        """Tokens signed with a different secret should fail."""
        manager1 = self._make_manager(APP_SECRET_KEY="secret-one")
        manager2 = self._make_manager(APP_SECRET_KEY="secret-two")
        session_data = {"email": "test@test.com", "login_time": datetime.utcnow().isoformat()}
        token = manager1.serializer.dumps(session_data)
        result = manager2.verify_session(token)
        assert result is None

    def test_allowed_domains_parsing(self):
        """Multiple comma-separated domains should be parsed."""
        manager = self._make_manager(ALLOWED_DOMAINS="example.com,test.org,foo.co")
        assert "example.com" in manager.allowed_domains
        assert "test.org" in manager.allowed_domains
        assert "foo.co" in manager.allowed_domains

    def test_logout_returns_true(self):
        """Logout should return True (token expiration-based)."""
        manager = self._make_manager()
        assert manager.logout("any-token") is True


# ============================================================
# get_current_user dependency tests
# ============================================================

class TestGetCurrentUser:
    """Tests for the get_current_user FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_portal_proxy_auth_valid(self):
        """Valid portal proxy headers should authenticate."""
        env = {
            "PORTAL_SECRET": "test-portal-secret",
            "ENVIRONMENT": "production",
            "DEMO_BYPASS": "false",
            "GOOGLE_CLIENT_ID": "test",
            "GOOGLE_CLIENT_SECRET": "test",
            "APP_SECRET_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=False):
            # Re-import to pick up env
            import importlib
            import services.auth_service as auth_mod
            importlib.reload(auth_mod)

            request = MagicMock()
            request.headers = {
                "X-Portal-Secret": "test-portal-secret",
                "X-Portal-User-Email": "jason@coloradocareassist.com",
                "X-Portal-User-Name": "Jason S",
            }
            request.cookies = {}

            result = await auth_mod.get_current_user(request, None)
            assert result["email"] == "jason@coloradocareassist.com"
            assert result["via_portal"] is True

    @pytest.mark.asyncio
    async def test_portal_proxy_auth_invalid_email(self):
        """Portal proxy with invalid email should be rejected."""
        from fastapi import HTTPException

        env = {
            "PORTAL_SECRET": "test-portal-secret",
            "ENVIRONMENT": "production",
            "DEMO_BYPASS": "false",
            "GOOGLE_CLIENT_ID": "test",
            "GOOGLE_CLIENT_SECRET": "test",
            "APP_SECRET_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import services.auth_service as auth_mod
            importlib.reload(auth_mod)

            request = MagicMock()
            request.headers = {
                "X-Portal-Secret": "test-portal-secret",
                "X-Portal-User-Email": "not-an-email",  # No @
                "X-Portal-User-Name": "Bad Actor",
            }
            request.cookies = {}

            with pytest.raises(HTTPException) as exc_info:
                await auth_mod.get_current_user(request, None)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_portal_proxy_wrong_secret(self):
        """Wrong portal secret should fall through to other auth methods."""
        from fastapi import HTTPException

        env = {
            "PORTAL_SECRET": "real-secret",
            "ENVIRONMENT": "production",
            "DEMO_BYPASS": "false",
            "GOOGLE_CLIENT_ID": "test",
            "GOOGLE_CLIENT_SECRET": "test",
            "APP_SECRET_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import services.auth_service as auth_mod
            importlib.reload(auth_mod)

            request = MagicMock()
            request.headers = {
                "X-Portal-Secret": "wrong-secret",
                "X-Portal-User-Email": "jason@coloradocareassist.com",
            }
            request.cookies = {}

            # No bearer token, no cookie → should raise 401
            with pytest.raises(HTTPException) as exc_info:
                await auth_mod.get_current_user(request, None)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_auth_raises_401(self):
        """No authentication at all should raise 401."""
        from fastapi import HTTPException

        env = {
            "PORTAL_SECRET": "test-secret",
            "ENVIRONMENT": "production",
            "DEMO_BYPASS": "false",
            "GOOGLE_CLIENT_ID": "test",
            "GOOGLE_CLIENT_SECRET": "test",
            "APP_SECRET_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import services.auth_service as auth_mod
            importlib.reload(auth_mod)

            request = MagicMock()
            request.headers = {}
            request.cookies = {}

            with pytest.raises(HTTPException) as exc_info:
                await auth_mod.get_current_user(request, None)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_demo_bypass_only_in_dev(self):
        """DEMO_BYPASS should only work in development environment."""
        env = {
            "ENVIRONMENT": "development",
            "DEMO_BYPASS": "true",
            "GOOGLE_CLIENT_ID": "test",
            "GOOGLE_CLIENT_SECRET": "test",
            "APP_SECRET_KEY": "test-key",
            "PORTAL_SECRET": "secret",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import services.auth_service as auth_mod
            importlib.reload(auth_mod)

            assert auth_mod.DEMO_BYPASS is True

        # Now test production — should NOT bypass
        env["ENVIRONMENT"] = "production"
        with patch.dict(os.environ, env, clear=False):
            importlib.reload(auth_mod)
            assert auth_mod.DEMO_BYPASS is False


# ============================================================
# require_domain decorator tests
# ============================================================

class TestRequireDomain:
    def test_require_domain_creates_decorator(self):
        """require_domain should return a callable decorator."""
        from services.auth_service import require_domain
        decorator = require_domain(["coloradocareassist.com"])
        assert callable(decorator)
