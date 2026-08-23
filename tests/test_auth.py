"""Unit and Integration Tests for Authentication, JWT Lifecycle, and Route Protection."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.core.auth_database import auth_db_manager
from app.core.security import hash_password, verify_password
from app.main import app


@pytest.fixture(autouse=True)
async def reset_auth_db():
    """Ensure in-memory auth tables or state are clean for tests."""
    auth_db_manager._in_memory_users.clear()
    auth_db_manager._in_memory_blacklist.clear()
    auth_db_manager._in_memory_reset_tokens.clear()
    yield


@pytest.mark.asyncio
async def test_argon2_password_hashing():
    """Verifies Argon2id password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


@pytest.mark.asyncio
async def test_user_signup_and_duplicate_rejection():
    """Tests user registration and duplicate email protection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Successful Signup
        payload = {
            "email": "dr.smith@medtech.com",
            "full_name": "Dr. John Smith",
            "password": "SecurePassword123!",
        }
        res = await client.post("/auth/signup", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "dr.smith@medtech.com"
        assert data["full_name"] == "Dr. John Smith"
        assert "id" in data
        assert "password" not in data
        assert "hashed_password" not in data

        # 2. Duplicate Registration Attempt
        dup_res = await client.post("/auth/signup", json=payload)
        assert dup_res.status_code == 400
        assert "already exists" in dup_res.json()["detail"]


@pytest.mark.asyncio
async def test_user_login_and_token_generation():
    """Tests login with OAuth2 form data and JWT token generation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        await client.post(
            "/auth/signup",
            json={
                "email": "sarah.connor@biomed.org",
                "full_name": "Sarah Connor",
                "password": "MySecretPass999!",
            },
        )

        # 1. Successful Login
        login_res = await client.post(
            "/auth/login",
            data={"username": "sarah.connor@biomed.org", "password": "MySecretPass999!"},
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["user"]["email"] == "sarah.connor@biomed.org"

        # 2. Invalid Credentials
        invalid_res = await client.post(
            "/auth/login",
            data={"username": "sarah.connor@biomed.org", "password": "WrongPassword!"},
        )
        assert invalid_res.status_code == 401
        assert "Incorrect email or password" in invalid_res.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_user_profile_and_revocation():
    """Tests /auth/me profile retrieval and token blacklisting upon logout."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register & Login
        await client.post(
            "/auth/signup",
            json={
                "email": "alex.chen@regulations.gov",
                "full_name": "Alex Chen",
                "password": "ValidPassword123!",
            },
        )
        login_res = await client.post(
            "/auth/login",
            data={"username": "alex.chen@regulations.gov", "password": "ValidPassword123!"},
        )
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 1. Fetch Profile (/auth/me)
        me_res = await client.get("/auth/me", headers=auth_headers)
        assert me_res.status_code == 200
        profile = me_res.json()
        assert profile["email"] == "alex.chen@regulations.gov"
        assert profile["full_name"] == "Alex Chen"

        # 2. Logout (/auth/logout)
        logout_res = await client.post("/auth/logout", headers=auth_headers)
        assert logout_res.status_code == 200
        assert "revoked" in logout_res.json()["message"]

        # 3. Attempt /auth/me with revoked token -> 401 Unauthorized
        revoked_me_res = await client.get("/auth/me", headers=auth_headers)
        assert revoked_me_res.status_code == 401
        assert "revoked" in revoked_me_res.json()["detail"]


@pytest.mark.asyncio
async def test_forgot_and_reset_password_workflow():
    """Tests complete forgot password token issuance and password reset."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        email = "elena.rostova@meddevices.eu"
        await client.post(
            "/auth/signup",
            json={
                "email": email,
                "full_name": "Elena Rostova",
                "password": "OriginalPassword123!",
            },
        )

        # 1. Forgot Password Request
        forgot_res = await client.post(
            "/auth/forgot-password",
            json={"email": email},
        )
        assert forgot_res.status_code == 200
        reset_token = forgot_res.json().get("reset_token")
        assert reset_token is not None

        # 2. Reset Password
        reset_res = await client.post(
            "/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "BrandNewSecurePassword456!",
            },
        )
        assert reset_res.status_code == 200
        assert "successfully" in reset_res.json()["message"]

        # 3. Old Password Fails
        old_login_res = await client.post(
            "/auth/login",
            data={"username": email, "password": "OriginalPassword123!"},
        )
        assert old_login_res.status_code == 401

        # 4. New Password Succeeds
        new_login_res = await client.post(
            "/auth/login",
            data={"username": email, "password": "BrandNewSecurePassword456!"},
        )
        assert new_login_res.status_code == 200
        assert "access_token" in new_login_res.json()

        # 5. Reusing Token Fails
        reuse_res = await client.post(
            "/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "AnotherNewPassword789!",
            },
        )
        assert reuse_res.status_code == 400
        assert "invalid" in reuse_res.json()["detail"].lower() or "used" in reuse_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_protected_endpoints_unauthorized_rejection():
    """Verifies that protected agent endpoints reject unauthenticated requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. /generic_chat without token
        chat_res = await client.post("/generic_chat", json={"user_input": "Hello agent"})
        assert chat_res.status_code == 401

        # 2. /research/run without token
        research_res = await client.post("/research/run", json={"topic": "FDA 510k"})
        assert research_res.status_code == 401

        # 3. /get_sql_query without token
        sql_res = await client.post("/get_sql_query", json={"query": "Show devices"})
        assert sql_res.status_code == 401
