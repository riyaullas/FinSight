from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models import User
from app.services.metrics import Period, dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    start: date | None = Query(None, description="Period start (inclusive). Defaults to the first of this month."),
    end: date | None = Query(None, description="Period end (inclusive). Defaults to today."),
    user: User = Depends(require_permission("dashboard:read")),
    db: Session = Depends(get_db),
) -> dict:
    period = None
    if start or end:
        if not (start and end):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide both start and end")
        if end < start or (end - start).days > 366:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Period must be between 1 and 367 days")
        period = Period(start, end)
    return dashboard(db, user.company, period)
