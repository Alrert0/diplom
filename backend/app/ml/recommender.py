"""SVD-based collaborative filtering recommender with TF-IDF content-based fallback."""

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "ml_models"
SVD_PATH = MODELS_DIR / "recommender.joblib"
TFIDF_PATH = MODELS_DIR / "tfidf_recommender.joblib"


class BookRecommender:
    """Collaborative filtering (SVD) + content-based (TF-IDF) recommender."""

    def __init__(self):
        self.svd_model = None
        self.trainset = None
        self.tfidf_matrix = None
        self.tfidf_vectorizer = None
        self.tfidf_book_ids: list[int] = []
        self._ratings_count_at_train = 0

    # ------------------------------------------------------------------
    # Collaborative filtering (SVD via scikit-surprise)
    # ------------------------------------------------------------------

    def train(self, ratings_data: list[tuple[int, int, float]]) -> dict:
        """Train SVD model on (user_id, book_id, score) tuples.

        Returns dict with RMSE metric.
        """
        try:
            from surprise import SVD, Dataset, Reader, accuracy
            from surprise.model_selection import cross_validate
        except ImportError:
            logger.warning("scikit-surprise not installed — SVD training skipped")
            return {"error": "scikit-surprise not installed", "count": len(ratings_data)}

        if len(ratings_data) < 5:
            logger.warning("Not enough ratings (%d) to train SVD", len(ratings_data))
            return {"error": "not_enough_data", "count": len(ratings_data)}

        reader = Reader(rating_scale=(1, 5))
        data = Dataset.load_from_df(
            _to_dataframe(ratings_data), reader
        )

        algo = SVD(n_factors=50, n_epochs=20, lr_all=0.005, reg_all=0.02)

        # Cross-validate for metrics
        cv_results = cross_validate(algo, data, measures=["RMSE", "MAE"], cv=min(5, len(ratings_data) // 3 or 2), verbose=False)

        # Train on full dataset
        trainset = data.build_full_trainset()
        algo.fit(trainset)

        self.svd_model = algo
        self.trainset = trainset
        self._ratings_count_at_train = len(ratings_data)

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": algo,
                "trainset": trainset,
                "ratings_count": len(ratings_data),
            },
            SVD_PATH,
        )
        logger.info("SVD model trained on %d ratings, saved to %s", len(ratings_data), SVD_PATH)

        return {
            "rmse": float(np.mean(cv_results["test_rmse"])),
            "mae": float(np.mean(cv_results["test_mae"])),
            "n_ratings": len(ratings_data),
        }

    def predict(self, user_id: int, book_ids: list[int]) -> list[tuple[int, float]]:
        """Predict ratings for given book_ids. Returns [(book_id, score)] sorted desc."""
        if self.svd_model is None:
            return []

        predictions = []
        for bid in book_ids:
            pred = self.svd_model.predict(user_id, bid)
            predictions.append((bid, pred.est))

        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions

    def get_recommendations(self, user_id: int, all_book_ids: list[int],
                            rated_book_ids: set[int], n: int = 10) -> list[int]:
        """Return top N recommended book IDs (excluding already rated)."""
        unrated = [bid for bid in all_book_ids if bid not in rated_book_ids]
        if not unrated:
            return []

        predictions = self.predict(user_id, unrated)
        return [bid for bid, _ in predictions[:n]]

    # ------------------------------------------------------------------
    # Content-based fallback (TF-IDF on descriptions)
    # ------------------------------------------------------------------

    def train_content_based(self, books_data: list[tuple[int, str]]):
        """Train TF-IDF vectors on (book_id, description) pairs."""
        if not books_data:
            return

        self.tfidf_book_ids = [b[0] for b in books_data]
        descriptions = [b[1] or "" for b in books_data]

        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000, stop_words="english", ngram_range=(1, 2)
        )
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(descriptions)

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "vectorizer": self.tfidf_vectorizer,
                "matrix": self.tfidf_matrix,
                "book_ids": self.tfidf_book_ids,
            },
            TFIDF_PATH,
        )
        logger.info("TF-IDF content model trained on %d books", len(books_data))

    def content_based_recommendations(
        self, liked_book_ids: list[int], rated_book_ids: set[int], n: int = 10
    ) -> list[int]:
        """Recommend books similar to liked ones using TF-IDF cosine similarity."""
        if self.tfidf_matrix is None or not liked_book_ids:
            return []

        # Find indices of liked books
        id_to_idx = {bid: i for i, bid in enumerate(self.tfidf_book_ids)}
        liked_indices = [id_to_idx[bid] for bid in liked_book_ids if bid in id_to_idx]
        if not liked_indices:
            return []

        # Average the TF-IDF vectors of liked books
        liked_vector = self.tfidf_matrix[liked_indices].mean(axis=0)
        similarities = cosine_similarity(liked_vector, self.tfidf_matrix).flatten()

        # Sort by similarity, exclude already rated
        ranked = np.argsort(similarities)[::-1]
        results = []
        for idx in ranked:
            bid = self.tfidf_book_ids[idx]
            if bid not in rated_book_ids:
                results.append(bid)
                if len(results) >= n:
                    break

        return results

    # ------------------------------------------------------------------
    # Load / utility
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load saved models from disk. Returns True if SVD model loaded."""
        loaded_svd = False
        if SVD_PATH.exists():
            try:
                data = joblib.load(SVD_PATH)
                self.svd_model = data["model"]
                self.trainset = data["trainset"]
                self._ratings_count_at_train = data.get("ratings_count", 0)
                loaded_svd = True
                logger.info("SVD model loaded from %s", SVD_PATH)
            except Exception:
                logger.exception("Failed to load SVD model")

        if TFIDF_PATH.exists():
            try:
                data = joblib.load(TFIDF_PATH)
                self.tfidf_vectorizer = data["vectorizer"]
                self.tfidf_matrix = data["matrix"]
                self.tfidf_book_ids = data["book_ids"]
                logger.info("TF-IDF model loaded from %s", TFIDF_PATH)
            except Exception:
                logger.exception("Failed to load TF-IDF model")

        return loaded_svd

    def needs_retrain(self, current_ratings_count: int, min_new_ratings: int = 10) -> bool:
        """Check if enough new ratings have accumulated to justify retraining."""
        return current_ratings_count - self._ratings_count_at_train >= min_new_ratings


def _to_dataframe(ratings_data: list[tuple[int, int, float]]):
    """Convert ratings list to pandas DataFrame for surprise."""
    import pandas as pd

    return pd.DataFrame(ratings_data, columns=["user_id", "book_id", "score"])
