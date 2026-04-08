"""ML metrics and visualization endpoints for diploma thesis."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ml-metrics"])


@router.get("/metrics")
async def get_ml_metrics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all ML evaluation metrics for diploma report."""
    try:
        from app.ml.metrics import generate_diploma_report

        report = await generate_diploma_report(db)
        return report
    except Exception:
        logger.exception("Error generating ML metrics")
        raise HTTPException(status_code=500, detail="Failed to generate metrics")


@router.get("/clustering-visualization")
async def get_clustering_visualization(
    user: User = Depends(get_current_user),
):
    """Return t-SNE scatter plot data for reader clusters."""
    try:
        from app.services.recommendation_service import _clustering, _ensure_loaded

        _ensure_loaded()
        return _clustering.visualize()
    except Exception:
        logger.exception("Error getting clustering visualization")
        raise HTTPException(status_code=500, detail="Failed to get visualization data")
