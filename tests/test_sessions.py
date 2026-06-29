import unittest
from datetime import date, timedelta
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.journey import FocusSession


class SessionExecutionTest(unittest.TestCase):
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
        self.token = self._register("linh@example.com")
        self.week_start = date.today() - timedelta(days=date.today().weekday())

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _register(self, email: str) -> str:
        response = self.client.post(
            "/auth/register",
            json={"name": "Linh Nguyen", "email": email, "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["accessToken"]

    def _auth(self, token: Optional[str] = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token or self.token}"}

    def _accepted_session(self, token: Optional[str] = None) -> str:
        token = token or self.token
        journey = self.client.post(
            "/journeys",
            headers=self._auth(token),
            json={"weekStart": self.week_start.isoformat(), "title": "A calm week"},
        ).json()
        session = self.client.post(
            f"/journeys/{journey['id']}/sessions",
            headers=self._auth(token),
            json={"title": "Write proposal", "category": "work", "priority": "high", "estimatedMinutes": 45},
        ).json()
        accept = self.client.post(
            f"/journeys/{journey['id']}/accept",
            headers=self._auth(token),
            json={"days": [{"date": date.today().isoformat(), "sessions": [{"sessionId": session["id"], "suggestedTime": "09:00"}]}]},
        )
        self.assertEqual(accept.status_code, 200)
        return session["id"]

    def test_today_returns_scheduled_sessions_for_current_user(self):
        session_id = self._accepted_session()

        response = self.client.get("/sessions/today", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], date.today().isoformat())
        self.assertEqual(body["sessions"][0]["id"], session_id)
        self.assertEqual(body["sessions"][0]["status"], "scheduled")

    def test_today_excludes_sessions_from_archived_journey(self):
        archived_session_id = self._accepted_session()
        active_session_id = self._accepted_session()

        response = self.client.get("/sessions/today", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        ids = [session["id"] for session in response.json()["sessions"]]
        self.assertNotIn(archived_session_id, ids)
        self.assertIn(active_session_id, ids)

    def test_session_detail_requires_ownership(self):
        session_id = self._accepted_session()
        other_token = self._register("minh@example.com")

        owned = self.client.get(f"/sessions/{session_id}", headers=self._auth())
        foreign = self.client.get(f"/sessions/{session_id}", headers=self._auth(other_token))

        self.assertEqual(owned.status_code, 200)
        self.assertEqual(owned.json()["id"], session_id)
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.json()["error"]["code"], "not_found")

    def test_other_user_cannot_mutate_session(self):
        session_id = self._accepted_session()
        other_token = self._register("minh@example.com")

        complete = self.client.post(f"/sessions/{session_id}/complete", headers=self._auth(other_token))
        undo = self.client.post(f"/sessions/{session_id}/undo-complete", headers=self._auth(other_token))
        skip = self.client.post(f"/sessions/{session_id}/skip", headers=self._auth(other_token))

        self.assertEqual(complete.status_code, 404)
        self.assertEqual(undo.status_code, 404)
        self.assertEqual(skip.status_code, 404)

    def test_complete_session_sets_completed_at_and_opens_reflection(self):
        session_id = self._accepted_session()

        response = self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sessionId"], session_id)
        self.assertEqual(body["status"], "completed")
        self.assertTrue(body["openReflection"])
        self.assertIsNotNone(body["completedAt"])
        with self.SessionLocal() as db:
            stored = db.get(FocusSession, session_id)
            self.assertEqual(stored.status, "completed")
            self.assertIsNotNone(stored.completed_at)

    def test_duplicate_complete_is_rejected_without_corrupting_session(self):
        session_id = self._accepted_session()
        self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        response = self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_state")
        with self.SessionLocal() as db:
            stored = db.get(FocusSession, session_id)
            self.assertEqual(stored.status, "completed")

    def test_undo_complete_returns_session_to_scheduled(self):
        session_id = self._accepted_session()
        self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        response = self.client.post(f"/sessions/{session_id}/undo-complete", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "scheduled")
        self.assertIsNone(response.json()["completedAt"])
        with self.SessionLocal() as db:
            stored = db.get(FocusSession, session_id)
            self.assertEqual(stored.status, "scheduled")
            self.assertIsNone(stored.completed_at)

    def test_skip_session_sets_skipped_at(self):
        session_id = self._accepted_session()

        response = self.client.post(f"/sessions/{session_id}/skip", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "skipped")
        self.assertIsNotNone(response.json()["skippedAt"])
        with self.SessionLocal() as db:
            stored = db.get(FocusSession, session_id)
            self.assertEqual(stored.status, "skipped")
            self.assertIsNotNone(stored.skipped_at)


if __name__ == "__main__":
    unittest.main()
