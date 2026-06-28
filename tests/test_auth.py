import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.user import User


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(self.engine)

        def override_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_register_returns_token_and_hashes_password(self):
        response = self.client.post(
            "/auth/register",
            json={"name": "Linh Nguyen", "email": "linh@example.com", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("accessToken", body)
        self.assertEqual(body["user"]["email"], "linh@example.com")

        with self.SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "linh@example.com"))
            self.assertIsNotNone(user)
            self.assertNotEqual(user.hashed_password, "secret123")

    def test_duplicate_email_returns_conflict_error(self):
        payload = {"name": "Linh Nguyen", "email": "linh@example.com", "password": "secret123"}
        self.client.post("/auth/register", json=payload)

        response = self.client.post("/auth/register", json=payload)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "duplicate_email")

    def test_login_and_current_user_use_database_backed_token(self):
        payload = {"name": "Linh Nguyen", "email": "linh@example.com", "password": "secret123"}
        self.client.post("/auth/register", json=payload)

        login = self.client.post(
            "/auth/login",
            json={"email": "linh@example.com", "password": "secret123"},
        )

        self.assertEqual(login.status_code, 200)
        token = login.json()["accessToken"]
        me = self.client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "linh@example.com")

    def test_bad_credentials_and_missing_token_are_rejected(self):
        response = self.client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "bad_credentials")

        me = self.client.get("/users/me")

        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.json()["error"]["code"], "missing_token")

    def test_invalid_payload_uses_error_shape(self):
        response = self.client.post(
            "/auth/register",
            json={"name": "", "email": "not-an-email", "password": "123"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertNotIn("123", str(response.json()))

    def test_whitespace_name_is_rejected(self):
        response = self.client.post(
            "/auth/register",
            json={"name": "   ", "email": "linh@example.com", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_logout_revokes_current_token(self):
        register = self.client.post(
            "/auth/register",
            json={"name": "Linh Nguyen", "email": "linh@example.com", "password": "secret123"},
        )
        token = register.json()["accessToken"]

        logout = self.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        me = self.client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.json()["error"]["code"], "invalid_token")


if __name__ == "__main__":
    unittest.main()
