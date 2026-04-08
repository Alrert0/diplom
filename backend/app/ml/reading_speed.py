"""XGBoost-based reading speed prediction model."""

import logging
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "ml_models"
MODEL_PATH = MODELS_DIR / "speed_model.joblib"

DEFAULT_WPM = 200.0

# Genre encoding for feature vector
GENRE_MAP = {
    "fiction": 0, "non-fiction": 1, "science": 2, "history": 3,
    "fantasy": 4, "romance": 5, "thriller": 6, "mystery": 7,
    "biography": 8, "philosophy": 9, "poetry": 10, "children": 11,
    "technology": 12, "self-help": 13, "horror": 14, "adventure": 15,
}


class ReadingSpeedPredictor:
    """Predict per-user reading speed (WPM) using XGBoost regression."""

    def __init__(self):
        self.model = None
        self._sessions_count_at_train = 0

    def train(self, sessions_data: list[dict]) -> dict:
        """Train XGBoost model on reading session data.

        Each dict in sessions_data should have:
            chapter_word_count, genre, hour_of_day, day_of_week,
            user_avg_speed, user_total_sessions, actual_wpm
        Returns metrics dict.
        """
        from xgboost import XGBRegressor
        from sklearn.model_selection import cross_val_score

        if len(sessions_data) < 10:
            logger.warning("Not enough sessions (%d) to train speed model", len(sessions_data))
            return {"error": "not_enough_data", "count": len(sessions_data)}

        X, y = _prepare_features(sessions_data)

        model = XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )

        # Cross-validate for metrics
        cv_folds = min(5, len(sessions_data) // 5 or 2)
        if cv_folds >= 2:
            mae_scores = cross_val_score(model, X, y, cv=cv_folds, scoring="neg_mean_absolute_error")
            mae = float(-np.mean(mae_scores))
        else:
            mae = 0.0

        # Train on full dataset
        model.fit(X, y)
        self.model = model
        self._sessions_count_at_train = len(sessions_data)

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": model, "sessions_count": len(sessions_data)},
            MODEL_PATH,
        )
        logger.info("Speed model trained on %d sessions, MAE=%.1f WPM", len(sessions_data), mae)

        return {
            "mae_wpm": mae,
            "n_sessions": len(sessions_data),
        }

    def predict(
        self,
        chapter_word_count: int,
        genre: str | None,
        hour_of_day: int,
        day_of_week: int,
        user_avg_speed: float,
        user_total_sessions: int,
    ) -> float:
        """Predict WPM for a reading session. Falls back to DEFAULT_WPM."""
        if self.model is None or user_total_sessions < 5:
            return user_avg_speed if user_avg_speed > 0 else DEFAULT_WPM

        features = _build_feature_vector(
            chapter_word_count, genre, hour_of_day, day_of_week,
            user_avg_speed, user_total_sessions,
        )
        pred = float(self.model.predict(np.array([features]))[0])
        # Clamp to reasonable range
        return max(50.0, min(1500.0, pred))

    def estimate_time(self, words_remaining: int, predicted_wpm: float) -> int:
        """Estimate minutes to read remaining words."""
        if predicted_wpm <= 0:
            predicted_wpm = DEFAULT_WPM
        return max(1, round(words_remaining / predicted_wpm))

    def load(self) -> bool:
        """Load saved model from disk."""
        if MODEL_PATH.exists():
            try:
                data = joblib.load(MODEL_PATH)
                self.model = data["model"]
                self._sessions_count_at_train = data.get("sessions_count", 0)
                logger.info("Speed model loaded from %s", MODEL_PATH)
                return True
            except Exception:
                logger.exception("Failed to load speed model")
        return False

    def needs_retrain(self, current_sessions_count: int, min_new: int = 50) -> bool:
        return current_sessions_count - self._sessions_count_at_train >= min_new


def _build_feature_vector(
    chapter_word_count: int,
    genre: str | None,
    hour_of_day: int,
    day_of_week: int,
    user_avg_speed: float,
    user_total_sessions: int,
) -> list[float]:
    genre_code = GENRE_MAP.get((genre or "").lower(), len(GENRE_MAP))
    return [
        float(chapter_word_count),
        float(genre_code),
        float(hour_of_day),
        float(day_of_week),
        float(user_avg_speed) if user_avg_speed > 0 else DEFAULT_WPM,
        float(user_total_sessions),
    ]


def _prepare_features(sessions_data: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    X = []
    y = []
    for s in sessions_data:
        X.append(_build_feature_vector(
            s["chapter_word_count"],
            s.get("genre"),
            s.get("hour_of_day", 12),
            s.get("day_of_week", 0),
            s.get("user_avg_speed", DEFAULT_WPM),
            s.get("user_total_sessions", 0),
        ))
        y.append(float(s["actual_wpm"]))
    return np.array(X), np.array(y)
