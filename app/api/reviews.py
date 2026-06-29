from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.core.errors import api_error
from app.models.journey import FocusSession, Reflection, WeeklyJourney
from app.models.user import User

router = APIRouter()

MOODS = ("energized", "balanced", "challenged")


class MoodSummary(BaseModel):
    energized: int
    balanced: int
    challenged: int


class ReviewInsight(BaseModel):
    source: str
    text: str


class WeeklyReviewResponse(BaseModel):
    journeyId: str
    sessionsCompleted: int
    reflectionCount: int
    moodSummary: MoodSummary
    insight: ReviewInsight
    recommendation: str


def _raise(code: str, message: str, status_code: int) -> None:
    raise HTTPException(status_code=status_code, detail=api_error(code, message))


def _owned_journey(journey_id: str, user: User, db: Session) -> WeeklyJourney:
    journey = db.get(WeeklyJourney, journey_id)
    if not journey or journey.user_id != user.id:
        _raise("not_found", "Journey was not found.", status.HTTP_404_NOT_FOUND)
    return journey


@router.get("/journeys/{journey_id}/review", response_model=WeeklyReviewResponse)
def journey_review(journey_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WeeklyReviewResponse:
    journey = _owned_journey(journey_id, user, db)
    sessions_completed = db.scalar(
        select(func.count())
        .select_from(FocusSession)
        .where(FocusSession.user_id == user.id, FocusSession.journey_id == journey.id, FocusSession.status == "completed")
    ) or 0
    reflections = list(
        db.scalars(select(Reflection).where(Reflection.user_id == user.id, Reflection.journey_id == journey.id))
    )
    mood_counts = {mood: 0 for mood in MOODS}
    for reflection in reflections:
        if reflection.mood in mood_counts:
            mood_counts[reflection.mood] += 1
    insight_text, recommendation = _review_copy(sessions_completed, mood_counts)
    return WeeklyReviewResponse(
        journeyId=journey.id,
        sessionsCompleted=sessions_completed,
        reflectionCount=len(reflections),
        moodSummary=MoodSummary(**mood_counts),
        insight=ReviewInsight(source="fallback", text=insight_text),
        recommendation=recommendation,
    )


def _review_copy(sessions_completed: int, mood_counts: dict[str, int]) -> tuple[str, str]:
    if sessions_completed == 0 and sum(mood_counts.values()) == 0:
        return (
            "Your week is ready for a gentle first reflection when you have more data.",
            "Complete one focus session and write one short reflection to unlock a richer weekly review.",
        )
    if mood_counts["challenged"] > mood_counts["energized"] + mood_counts["balanced"]:
        return (
            "This week asked for more effort than ease. You still kept showing up.",
            "Plan next week with fewer high-priority sessions and a little more recovery space.",
        )
    return (
        "You made steady progress by protecting small focus windows.",
        "Plan next week with one clear high-priority focus and a little more breathing room.",
    )
