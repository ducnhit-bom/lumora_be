import unittest
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


class SettingsTest(unittest.TestCase):
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
        self.token = self._register("settings@test.com")

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _register(self, email: str) -> str:
        response = self.client.post(
            "/auth/register",
            json={"name": "Settings Tester", "email": email, "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["accessToken"]

    def _auth(self, token: Optional[str] = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token or self.token}"}

    def test_get_settings_returns_defaults(self):
        response = self.client.get("/settings", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["autoOpenReflection"])
        self.assertEqual(body["preferredFocusTime"], "09:00")
        self.assertEqual(body["maxSessionsPerDay"], 5)
        self.assertEqual(body["timezone"], "Asia/Ho_Chi_Minh")

    def test_update_all_settings(self):
        response = self.client.patch(
            "/settings",
            headers=self._auth(),
            json={
                "autoOpenReflection": False,
                "preferredFocusTime": "10:30",
                "maxSessionsPerDay": 3,
                "timezone": "America/New_York",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["autoOpenReflection"])
        self.assertEqual(body["preferredFocusTime"], "10:30")
        self.assertEqual(body["maxSessionsPerDay"], 3)
        self.assertEqual(body["timezone"], "America/New_York")

    def test_update_partial_only_changes_sent_fields(self):
        response = self.client.patch(
            "/settings",
            headers=self._auth(),
            json={"autoOpenReflection": False},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["autoOpenReflection"])
        self.assertEqual(body["preferredFocusTime"], "09:00")
        self.assertEqual(body["maxSessionsPerDay"], 5)

    def test_update_rejects_invalid_time_format(self):
        response = self.client.patch(
            "/settings",
            headers=self._auth(),
            json={"preferredFocusTime": "invalid"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_update_rejects_max_sessions_out_of_range(self):
        response = self.client.patch(
            "/settings",
            headers=self._auth(),
            json={"maxSessionsPerDay": 25},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_get_settings_lazy_creates_for_user_without_settings(self):
        other_token = self._register("new@test.com")

        response = self.client.get("/settings", headers=self._auth(other_token))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["autoOpenReflection"])
        self.assertEqual(body["preferredFocusTime"], "09:00")

    def test_settings_requires_auth(self):
        get_resp = self.client.get("/settings")
        self.assertEqual(get_resp.status_code, 401)

        patch_resp = self.client.patch("/settings", json={"autoOpenReflection": False})
        self.assertEqual(patch_resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
