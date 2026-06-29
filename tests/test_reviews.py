import unittest
from datetime import date, timedelta
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app


class WeeklyReviewTest(unittest.TestCase):
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

    def _accepted_journey(self, session_count: int = 1, token: Optional[str] = None) -> tuple[str, list[str]]:
        token = token or self.token
        journey = self.client.post(
            "/journeys",
            headers=self._auth(token),
            json={"weekStart": self.week_start.isoformat(), "title": "A calm week"},
        ).json()
        session_ids = []
        for index in range(session_count):
            session = self.client.post(
                f"/journeys/{journey['id']}/sessions",
                headers=self._auth(token),
                json={
                    "title": f"Focus {index + 1}",
                    "category": "work",
                    "priority": "high" if index == 0 else "medium",
                    "estimatedMinutes": 45,
                },
            ).json()
            session_ids.append(session["id"])
        accept = self.client.post(
            f"/journeys/{journey['id']}/accept",
            headers=self._auth(token),
            json={
                "days": [
                    {
                        "date": date.today().isoformat(),
                        "sessions": [
                            {"sessionId": session_id, "suggestedTime": f"{index + 9:02}:00"}
                            for index, session_id in enumerate(session_ids)
                        ],
                    }
                ]
            },
        )
        self.assertEqual(accept.status_code, 200)
        return journey["id"], session_ids

    def _complete_and_reflect(self, session_id: str, content: str, mood: Optional[str] = None) -> None:
        complete = self.client.post(f"/sessions/{session_id}/complete", headers=self._auth())
        self.assertEqual(complete.status_code, 200)
        payload = {"sessionId": session_id, "content": content}
        if mood is not None:
            payload["mood"] = mood
        reflection = self.client.post("/reflections", headers=self._auth(), json=payload)
        self.assertEqual(reflection.status_code, 200)

    def test_review_returns_empty_supportive_summary_for_owned_journey(self):
        journey_id, _ = self._accepted_journey()

        response = self.client.get(f"/journeys/{journey_id}/review", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["journeyId"], journey_id)
        self.assertEqual(body["sessionsCompleted"], 0)
        self.assertEqual(body["reflectionCount"], 0)
        self.assertEqual(body["moodSummary"], {"energized": 0, "balanced": 0, "challenged": 0})
        self.assertEqual(body["insight"]["source"], "fallback")
        self.assertIn("gentle first reflection", body["insight"]["text"])
        self.assertIn("Complete one focus session", body["recommendation"])

    def test_review_counts_completed_sessions_reflections_and_moods(self):
        journey_id, session_ids = self._accepted_journey(session_count=3)
        self._complete_and_reflect(session_ids[0], "I protected the first block.", "balanced")
        self._complete_and_reflect(session_ids[1], "It took effort.", "challenged")
        complete = self.client.post(f"/sessions/{session_ids[2]}/complete", headers=self._auth())
        self.assertEqual(complete.status_code, 200)

        response = self.client.get(f"/journeys/{journey_id}/review", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sessionsCompleted"], 3)
        self.assertEqual(body["reflectionCount"], 2)
        self.assertEqual(body["moodSummary"], {"energized": 0, "balanced": 1, "challenged": 1})
        self.assertIn("steady progress", body["insight"]["text"])

    def test_challenged_heavy_review_returns_recovery_recommendation(self):
        journey_id, session_ids = self._accepted_journey(session_count=2)
        self._complete_and_reflect(session_ids[0], "Hard but done.", "challenged")
        self._complete_and_reflect(session_ids[1], "Still difficult.", "challenged")

        response = self.client.get(f"/journeys/{journey_id}/review", headers=self._auth())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("more effort than ease", body["insight"]["text"])
        self.assertIn("fewer high-priority sessions", body["recommendation"])

    def test_other_user_cannot_read_review(self):
        journey_id, _ = self._accepted_journey()
        other_token = self._register("minh@example.com")

        response = self.client.get(f"/journeys/{journey_id}/review", headers=self._auth(other_token))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
