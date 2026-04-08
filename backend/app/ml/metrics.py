"""ML evaluation metrics for diploma thesis."""

import logging

import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    silhouette_score,
    calinski_harabasz_score,
    davies_bouldin_score,
)

logger = logging.getLogger(__name__)


def evaluate_recommender(recommender, ratings_data: list[tuple[int, int, float]]) -> dict:
    """Evaluate SVD recommender with 80/20 split.

    Returns {rmse, mae, precision_at_10, recall_at_10, n_users, n_items, n_ratings}.
    """
    try:
        from surprise import Dataset, Reader, accuracy
    except ImportError:
        return {"error": "scikit-surprise not installed", "n_ratings": len(ratings_data)}

    if len(ratings_data) < 10:
        return {"error": "not_enough_data", "n_ratings": len(ratings_data)}

    from app.ml.recommender import _to_dataframe

    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(_to_dataframe(ratings_data), reader)

    trainset = data.build_full_trainset()
    testset = trainset.build_testset()

    if recommender.svd_model is None:
        return {"error": "model_not_trained"}

    predictions = recommender.svd_model.test(testset)

    rmse = accuracy.rmse(predictions, verbose=False)
    mae = accuracy.mae(predictions, verbose=False)

    # Precision@10 and Recall@10
    # For each user: relevant = items rated >= 4, recommended = top 10 predicted
    from collections import defaultdict

    user_est = defaultdict(list)
    user_true = defaultdict(list)
    for pred in predictions:
        user_est[pred.uid].append((pred.iid, pred.est))
        user_true[pred.uid].append((pred.iid, pred.r_ui))

    precisions = []
    recalls = []
    threshold = 4.0

    for uid in user_est:
        # Top 10 predicted
        top_10 = sorted(user_est[uid], key=lambda x: x[1], reverse=True)[:10]
        # Relevant items (true rating >= threshold)
        relevant = {iid for iid, rating in user_true[uid] if rating >= threshold}

        if not relevant:
            continue

        recommended = {iid for iid, _ in top_10}
        n_relevant_recommended = len(recommended & relevant)

        precisions.append(n_relevant_recommended / len(recommended) if recommended else 0)
        recalls.append(n_relevant_recommended / len(relevant) if relevant else 0)

    unique_users = set()
    unique_items = set()
    for u, b, _ in ratings_data:
        unique_users.add(u)
        unique_items.add(b)

    return {
        "rmse": float(rmse),
        "mae": float(mae),
        "precision_at_10": float(np.mean(precisions)) if precisions else 0.0,
        "recall_at_10": float(np.mean(recalls)) if recalls else 0.0,
        "n_users": len(unique_users),
        "n_items": len(unique_items),
        "n_ratings": len(ratings_data),
    }


def evaluate_speed_predictor(predictor, test_data: list[dict]) -> dict:
    """Evaluate XGBoost reading speed model.

    Returns {mae, rmse, r2, n_samples}.
    """
    if predictor.model is None or len(test_data) < 5:
        return {"error": "model_not_trained_or_insufficient_data", "n_samples": len(test_data)}

    from app.ml.reading_speed import _prepare_features

    X, y_true = _prepare_features(test_data)
    y_pred = predictor.model.predict(X)

    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "n_samples": len(test_data),
    }


def evaluate_clustering(clustering) -> dict:
    """Evaluate KMeans clustering quality.

    Returns {silhouette, calinski_harabasz, davies_bouldin, n_clusters, n_users}.
    """
    if (
        clustering.kmeans is None
        or clustering.user_vectors is None
        or clustering.labels is None
        or clustering.scaler is None
    ):
        return {"error": "model_not_trained"}

    X_scaled = clustering.scaler.transform(clustering.user_vectors)
    labels = clustering.labels

    n_labels = len(set(labels))
    if n_labels < 2:
        return {"error": "single_cluster", "n_clusters": n_labels}

    return {
        "silhouette": float(silhouette_score(X_scaled, labels)),
        "calinski_harabasz": float(calinski_harabasz_score(X_scaled, labels)),
        "davies_bouldin": float(davies_bouldin_score(X_scaled, labels)),
        "n_clusters": int(clustering.k),
        "n_users": len(labels),
    }


async def generate_diploma_report(db) -> dict:
    """Run all evaluations and return combined metrics for diploma thesis."""
    from sqlalchemy import select

    from app.models.rating import Rating
    from app.models.reading import ReadingSession
    from app.models.book import Book, Chapter
    from app.services.recommendation_service import (
        _recommender, _speed_predictor, _clustering, _ensure_loaded,
    )
    from app.ml.reading_speed import DEFAULT_WPM

    _ensure_loaded()

    report: dict = {}

    # 1. Recommender metrics
    result = await db.execute(select(Rating.user_id, Rating.book_id, Rating.score))
    ratings_data = [(r[0], r[1], float(r[2])) for r in result.all()]
    report["recommender"] = evaluate_recommender(_recommender, ratings_data)

    # 2. Speed predictor metrics
    session_rows = await db.execute(
        select(
            ReadingSession.user_id,
            ReadingSession.words_read,
            ReadingSession.time_spent_seconds,
            ReadingSession.session_start,
            Chapter.word_count,
            Book.genre,
        )
        .join(Chapter, ReadingSession.chapter_id == Chapter.id)
        .join(Book, ReadingSession.book_id == Book.id)
        .where(ReadingSession.time_spent_seconds > 0)
    )
    raw = session_rows.all()
    sessions_data = []
    for s in raw:
        if s[2] <= 0:
            continue
        wpm = s[1] / s[2] * 60
        if wpm < 10 or wpm > 2000:
            continue
        sessions_data.append({
            "chapter_word_count": s[4],
            "genre": s[5],
            "hour_of_day": s[3].hour if s[3] else 12,
            "day_of_week": s[3].weekday() if s[3] else 0,
            "user_avg_speed": DEFAULT_WPM,
            "user_total_sessions": 0,
            "actual_wpm": wpm,
        })
    report["speed_predictor"] = evaluate_speed_predictor(_speed_predictor, sessions_data)

    # 3. Clustering metrics
    report["clustering"] = evaluate_clustering(_clustering)

    # 4. Dataset summary
    result = await db.execute(select(Book.id))
    n_books = len(result.all())
    report["dataset"] = {
        "n_books": n_books,
        "n_ratings": len(ratings_data),
        "n_reading_sessions": len(raw),
    }

    return report
