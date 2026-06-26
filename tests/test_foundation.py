import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import get_database_url
from app.core.errors import api_error
from app.main import app


class FoundationTest(unittest.TestCase):
    def test_settings_have_phase_one_defaults(self):
        settings = Settings()

        self.assertEqual(settings.app_name, "Lumora API")
        self.assertEqual(settings.environment, "development")
        self.assertNotIn("*", settings.cors_origins)

    def test_database_url_uses_settings_value(self):
        settings = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/lumora")

        self.assertEqual(get_database_url(settings), settings.database_url)

    def test_api_error_shape_matches_contract(self):
        response = api_error("invalid_state", "Cannot complete this session yet.")

        self.assertEqual(
            response,
            {
                "error": {
                    "code": "invalid_state",
                    "message": "Cannot complete this session yet.",
                    "details": {},
                }
            },
        )

    def test_app_exposes_health_endpoint(self):
        response = TestClient(app).get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_alembic_has_baseline_revision(self):
        versions = Path("alembic/versions")

        self.assertTrue(any(versions.glob("*.py")))


if __name__ == "__main__":
    unittest.main()
