"""Recommendations, reading time estimates, user stats, and model retraining."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.get("/recommendations")
async def get_recommendations(
    n: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Personalized book recommendations for the current user."""
    try:
        recs = await recommendation_service.get_recommendations(user.id, db, n=n)
        return {"recommendations": recs, "count": len(recs)}
    except Exception:
        logger.exception("Error generating recommendations for user %d", user.id)
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")


@router.get("/reading/time-estimate")
async def reading_time_estimate(
    book_id: int = Query(...),
    chapter: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Personalized reading time estimate for a chapter/book."""
    try:
        estimate = await recommendation_service.get_reading_time_estimate(
            user.id, book_id, chapter, db
        )
        return estimate
    except Exception:
        logger.exception("Error estimating reading time")
        raise HTTPException(status_code=500, detail="Failed to estimate reading time")


@router.get("/reading/stats")
async def user_reading_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User reading statistics."""
    try:
        stats = await recommendation_service.get_user_stats(user.id, db)
        return stats
    except Exception:
        logger.exception("Error fetching user stats")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")


@router.post("/ml/retrain")
async def retrain_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger retraining of all ML models."""
    try:
        results = await recommendation_service.retrain_models(db)
        return {"status": "ok", "results": results}
    except Exception:
        logger.exception("Error retraining models")
        raise HTTPException(status_code=500, detail="Model retraining failed")


@router.get("/ml/clustering/visualize")
async def clustering_visualization(
    user: User = Depends(get_current_user),
):
    """Return t-SNE visualization data for reader clusters."""
    from app.services.recommendation_service import _clustering
    recommendation_service._ensure_loaded()
    data = _clustering.visualize()
    return data
