"""Tests for environment validation — no mocks, real env var manipulation."""

import os
import pytest
from fastapi.testclient import TestClient


class TestValidateEnvironment:
    """Tests for validate_environment() function."""

    def test_validate_returns_dict(self):
        """validate_environment returns a dict with the expected keys."""
        from app.env_validation import validate_environment
        result = validate_environment()
        assert isinstance(result, dict)
        assert "environment" in result
        assert "critical" in result
        assert "warnings" in result
        assert "info" in result
        assert "valid" in result

    def test_development_mode_always_valid(self):
        """In development mode, validation always returns valid=True."""
        # Ensure we are NOT in production
        old = os.environ.pop("SIGNALDACH_ENV", None)
        try:
            from app.env_validation import validate_environment
            result = validate_environment()
            assert result["valid"] is True
            assert result["environment"] == "development"
        finally:
            if old is not None:
                os.environ["SIGNALDACH_ENV"] = old

    def test_critical_keys_listed(self):
        """All three critical keys appear in result['critical']."""
        from app.env_validation import validate_environment
        result = validate_environment()
        assert "SIGNALDACH_JWT_SECRET_KEY" in result["critical"]
        assert "SIGNALDACH_DATABASE_URL" in result["critical"]
        assert "SIGNALDACH_REDIS_URL" in result["critical"]

    def test_warning_when_no_ai_key(self):
        """Warns when neither OPENAI nor ANTHROPIC key is set."""
        old_openai = os.environ.pop("SIGNALDACH_OPENAI_API_KEY", None)
        old_anthropic = os.environ.pop("SIGNALDACH_ANTHROPIC_API_KEY", None)
        try:
            from app.env_validation import validate_environment
            result = validate_environment()
            ai_warnings = [w for w in result["warnings"] if "AI provider" in w]
            assert len(ai_warnings) >= 1, f"Expected AI provider warning, got: {result['warnings']}"
        finally:
            if old_openai is not None:
                os.environ["SIGNALDACH_OPENAI_API_KEY"] = old_openai
            if old_anthropic is not None:
                os.environ["SIGNALDACH_ANTHROPIC_API_KEY"] = old_anthropic

    def test_env_override_detected(self):
        """When SIGNALDACH_REDIS_URL is set, it shows as 'set'."""
        old = os.environ.get("SIGNALDACH_REDIS_URL")
        os.environ["SIGNALDACH_REDIS_URL"] = "redis://testhost:6379"
        try:
            from app.env_validation import validate_environment
            result = validate_environment()
            assert result["critical"]["SIGNALDACH_REDIS_URL"] == "set"
        finally:
            if old is not None:
                os.environ["SIGNALDACH_REDIS_URL"] = old
            else:
                os.environ.pop("SIGNALDACH_REDIS_URL", None)

    def test_production_raises_without_jwt(self):
        """Production mode raises EnvValidationError when JWT secret is dev default."""
        from app.env_validation import validate_environment, EnvValidationError
        old_env = os.environ.get("SIGNALDACH_ENV")
        old_jwt = os.environ.get("SIGNALDACH_JWT_SECRET_KEY")
        old_db = os.environ.get("SIGNALDACH_DATABASE_URL")
        old_redis = os.environ.get("SIGNALDACH_REDIS_URL")
        os.environ["SIGNALDACH_ENV"] = "production"
        # Clear JWT so it falls through to missing/default
        os.environ.pop("SIGNALDACH_JWT_SECRET_KEY", None)
        os.environ["SIGNALDACH_DATABASE_URL"] = "postgresql://u:p@host/db"
        os.environ["SIGNALDACH_REDIS_URL"] = "redis://localhost:6379"
        try:
            with pytest.raises(EnvValidationError):
                validate_environment()
        finally:
            if old_env is not None:
                os.environ["SIGNALDACH_ENV"] = old_env
            else:
                os.environ.pop("SIGNALDACH_ENV", None)
            if old_jwt is not None:
                os.environ["SIGNALDACH_JWT_SECRET_KEY"] = old_jwt
            else:
                os.environ.pop("SIGNALDACH_JWT_SECRET_KEY", None)
            if old_db is not None:
                os.environ["SIGNALDACH_DATABASE_URL"] = old_db
            else:
                os.environ.pop("SIGNALDACH_DATABASE_URL", None)
            if old_redis is not None:
                os.environ["SIGNALDACH_REDIS_URL"] = old_redis
            else:
                os.environ.pop("SIGNALDACH_REDIS_URL", None)

    def test_no_warning_when_ai_key_set(self):
        """No AI provider warning when at least one key is set."""
        old = os.environ.get("SIGNALDACH_ANTHROPIC_API_KEY")
        os.environ["SIGNALDACH_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        try:
            from app.env_validation import validate_environment
            result = validate_environment()
            ai_warnings = [w for w in result["warnings"] if "AI provider" in w]
            assert len(ai_warnings) == 0, f"Unexpected AI warning: {ai_warnings}"
        finally:
            if old is not None:
                os.environ["SIGNALDACH_ANTHROPIC_API_KEY"] = old
            else:
                os.environ.pop("SIGNALDACH_ANTHROPIC_API_KEY", None)


class TestHealthEnvEndpoint:
    """Tests for the /health/env HTTP endpoint."""

    def _get_client(self):
        from app.main import app
        return TestClient(app)

    def test_health_env_endpoint(self):
        """GET /health/env returns 200."""
        client = self._get_client()
        resp = client.get("/health/env")
        assert resp.status_code == 200
        data = resp.json()
        assert "environment" in data
        assert "valid" in data

    def test_health_env_has_warnings(self):
        """Response includes warnings list and warnings_count."""
        client = self._get_client()
        resp = client.get("/health/env")
        data = resp.json()
        assert "warnings" in data
        assert "warnings_count" in data
        assert isinstance(data["warnings"], list)
        assert data["warnings_count"] == len(data["warnings"])


class TestEnvExampleFile:
    """Tests for the .env.example file."""

    def test_env_example_file_exists(self):
        """.env.example exists in the backend directory and is not empty."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env.example")
        env_path = os.path.normpath(env_path)
        assert os.path.isfile(env_path), f".env.example not found at {env_path}"
        size = os.path.getsize(env_path)
        assert size > 100, f".env.example is too small ({size} bytes)"
