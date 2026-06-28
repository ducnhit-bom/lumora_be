import unittest
from datetime import date, timedelta
from typing import Optional

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.journey import FocusSession, WeeklyJourney


class JourneyTest(unittest.TestCase):
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

    def _create_journey(self, title: str = "A focused, calm week", week_start: Optional[date] = None) -> dict:
        response = self.client.post(
            "/journeys",
            headers=self._auth(),
            json={"weekStart": (week_start or self.week_start).isoformat(), "title": title},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _add_session(self, journey_id: str, title: str = "Write proposal outline") -> dict:
        response = self.client.post(
            f"/journeys/{journey_id}/sessions",
            headers=self._auth(),
            json={
                "title": title,
                "note": "Keep it simple",
                "category": "work",
                "priority": "high",
                "estimatedMinutes": 45,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_create_multiple_drafts_and_current_returns_newest_draft(self):
        first = self._create_journey("First draft")
        second = self._create_journey("Second draft")

        current = self.client.get("/journeys/current", headers=self._auth())

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["status"], "draft")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["id"], second["id"])
        self.assertEqual(current.json()["title"], "Second draft")

    def test_add_session_to_owned_draft(self):
        journey = self._create_journey()

        session = self._add_session(journey["id"])

        self.assertEqual(session["journeyId"], journey["id"])
        self.assertEqual(session["status"], "todo")
        self.assertIsNone(session["scheduledDate"])
        self.assertIsNone(session["scheduledTime"])

    def test_create_journey_normalizes_week_start_to_monday(self):
        tuesday = self.week_start + timedelta(days=1)

        journey = self._create_journey("Tuesday draft", week_start=tuesday)

        self.assertEqual(journey["weekStart"], self.week_start.isoformat())

    def test_other_user_cannot_access_or_mutate_journey(self):
        journey = self._create_journey()
        other_token = self._register("minh@example.com")

        current = self.client.get("/journeys/current", headers=self._auth(other_token))
        add = self.client.post(
            f"/journeys/{journey['id']}/sessions",
            headers=self._auth(other_token),
            json={"title": "Steal", "category": "work", "priority": "low", "estimatedMinutes": 15},
        )

        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json(), {"journey": None})
        self.assertEqual(add.status_code, 404)
        self.assertEqual(add.json()["error"]["code"], "not_found")

    def test_suggest_returns_preview_without_mutating_sessions(self):
        journey = self._create_journey()
        session = self._add_session(journey["id"])

        suggest = self.client.post(f"/journeys/{journey['id']}/suggest", headers=self._auth())

        self.assertEqual(suggest.status_code, 200)
        body = suggest.json()
        self.assertEqual(body["source"], "fallback")
        self.assertEqual(body["days"][0]["sessions"][0]["sessionId"], session["id"])
        with self.SessionLocal() as db:
            stored = db.get(FocusSession, session["id"])
            self.assertEqual(stored.status, "todo")
            self.assertIsNone(stored.scheduled_date)
            self.assertIsNone(stored.scheduled_time)

    def test_accept_persists_schedule_and_archives_previous_active(self):
        first = self._create_journey("First")
        first_session = self._add_session(first["id"], "Monday work")
        second = self._create_journey("Second")
        second_session = self._add_session(second["id"], "Tuesday work")

        first_accept = self.client.post(
            f"/journeys/{first['id']}/accept",
            headers=self._auth(),
            json={"days": [{"date": self.week_start.isoformat(), "sessions": [{"sessionId": first_session["id"], "suggestedTime": "09:00"}]}]},
        )
        second_day = self.week_start + timedelta(days=1)
        second_accept = self.client.post(
            f"/journeys/{second['id']}/accept",
            headers=self._auth(),
            json={"days": [{"date": second_day.isoformat(), "sessions": [{"sessionId": second_session["id"], "suggestedTime": "10:30"}]}]},
        )

        self.assertEqual(first_accept.status_code, 200)
        self.assertEqual(second_accept.status_code, 200)
        self.assertEqual(second_accept.json()["status"], "active")
        with self.SessionLocal() as db:
            first_journey = db.get(WeeklyJourney, first["id"])
            second_journey = db.get(WeeklyJourney, second["id"])
            stored_session = db.get(FocusSession, second_session["id"])
            self.assertEqual(first_journey.status, "archived")
            self.assertEqual(second_journey.status, "active")
            self.assertEqual(stored_session.status, "scheduled")
            self.assertEqual(stored_session.scheduled_date, second_day)
            self.assertEqual(stored_session.scheduled_time, "10:30")

    def test_invalid_accept_does_not_partially_update_sessions(self):
        journey = self._create_journey()
        session = self._add_session(journey["id"])

        response = self.client.post(
            f"/journeys/{journey['id']}/accept",
            headers=self._auth(),
            json={"days": [{"date": "2026-07-08", "sessions": [{"sessionId": session["id"], "suggestedTime": "99:99"}]}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_schedule")
        with self.SessionLocal() as db:
            stored_journey = db.get(WeeklyJourney, journey["id"])
            stored_session = db.get(FocusSession, session["id"])
            self.assertEqual(stored_journey.status, "draft")
            self.assertEqual(stored_session.status, "todo")
            self.assertIsNone(stored_session.scheduled_date)

    def test_accept_rejects_schedule_that_omits_existing_sessions(self):
        journey = self._create_journey()
        first = self._add_session(journey["id"], "First")
        second = self._add_session(journey["id"], "Second")

        response = self.client.post(
            f"/journeys/{journey['id']}/accept",
            headers=self._auth(),
            json={"days": [{"date": self.week_start.isoformat(), "sessions": [{"sessionId": first["id"], "suggestedTime": "09:00"}]}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_schedule")
        with self.SessionLocal() as db:
            omitted = db.get(FocusSession, second["id"])
            self.assertEqual(omitted.status, "todo")
            self.assertIsNone(omitted.scheduled_date)


if __name__ == "__main__":
    unittest.main()
