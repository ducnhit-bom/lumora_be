import unittest
from datetime import date, timedelta
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


class ReflectionTest(unittest.TestCase):
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

    def _accepted_session(self, token: Optional[str] = None) -> tuple[str, str]:
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
        return journey["id"], session["id"]

    def test_reflection_question_returns_fallback_for_owned_session(self):
        _, session_id = self._accepted_session()

        response = self.client.get(f"/sessions/{session_id}/reflection-question", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sessionId"], session_id)
        self.assertIn("question", body)
        self.assertGreater(len(body["question"]), 10)

    def test_other_user_cannot_read_reflection_question(self):
        _, session_id = self._accepted_session()
        other_token = self._register("minh@example.com")

        response = self.client.get(f"/sessions/{session_id}/reflection-question", headers=self._auth(other_token))

        self.assertEqual(response.status_code, 404)

    def test_create_reflection_and_list_by_journey(self):
        journey_id, session_id = self._accepted_session()
        self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        created = self.client.post(
            "/reflections",
            headers=self._auth(),
            json={"sessionId": session_id, "content": "I found one calm next step.", "mood": "balanced"},
        )
        listed = self.client.get(f"/journeys/{journey_id}/reflections", headers=self._auth())

        self.assertEqual(created.status_code, 200)
        created_body = created.json()
        self.assertEqual(created_body["sessionId"], session_id)
        self.assertEqual(created_body["journeyId"], journey_id)
        self.assertEqual(created_body["content"], "I found one calm next step.")
        self.assertEqual(created_body["mood"], "balanced")
        self.assertIn("createdAt", created_body)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["reflections"][0]["id"], created_body["id"])

    def test_create_reflection_allows_missing_mood(self):
        journey_id, session_id = self._accepted_session()
        self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        response = self.client.post(
            "/reflections",
            headers=self._auth(),
            json={"sessionId": session_id, "content": "Done."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["journeyId"], journey_id)
        self.assertIsNone(response.json()["mood"])

    def test_create_reflection_requires_completed_session(self):
        _, session_id = self._accepted_session()

        response = self.client.post(
            "/reflections",
            headers=self._auth(),
            json={"sessionId": session_id, "content": "Too early.", "mood": "balanced"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_state")

    def test_recomplete_existing_reflection_does_not_reopen_reflection(self):
        _, session_id = self._accepted_session()
        self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())
        self.client.post(
            "/reflections",
            headers=self._auth(),
            json={"sessionId": session_id, "content": "Done once.", "mood": "balanced"},
        )
        self.client.post(f"/sessions/{session_id}/undo-complete", headers=self._auth())

        response = self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["openReflection"])

    def test_create_reflection_rejects_content_over_500_chars(self):
        _, session_id = self._accepted_session()
        self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        response = self.client.post(
            "/reflections",
            headers=self._auth(),
            json={"sessionId": session_id, "content": "x" * 501, "mood": "energized"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_create_reflection_rejects_invalid_mood(self):
        _, session_id = self._accepted_session()
        self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())

        response = self.client.post(
            "/reflections",
            headers=self._auth(),
            json={"sessionId": session_id, "content": "Done.", "mood": "sad"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_other_user_cannot_create_or_list_reflections(self):
        journey_id, session_id = self._accepted_session()
        other_token = self._register("minh@example.com")

        created = self.client.post(
            "/reflections",
            headers=self._auth(other_token),
            json={"sessionId": session_id, "content": "Not mine.", "mood": "challenged"},
        )
        listed = self.client.get(f"/journeys/{journey_id}/reflections", headers=self._auth(other_token))

        self.assertEqual(created.status_code, 404)
        self.assertEqual(listed.status_code, 404)


if __name__ == "__main__":
    unittest.main()
