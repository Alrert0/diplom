"""KMeans reader clustering with t-SNE visualization."""

import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "ml_models"
MODEL_PATH = MODELS_DIR / "clustering.joblib"

# Genre list matching recommender.py
GENRES = [
    "fiction", "non-fiction", "science", "history", "fantasy", "romance",
    "thriller", "mystery", "biography", "philosophy", "poetry", "children",
    "technology", "self-help", "horror", "adventure",
]


class ReaderClustering:
    """KMeans clustering of readers by reading behavior."""

    def __init__(self):
        self.kmeans = None
        self.scaler = None
        self.user_ids: list[int] = []
        self.user_vectors: np.ndarray | None = None
        self.labels: np.ndarray | None = None
        self.tsne_coords: np.ndarray | None = None
        self.k = 0

    def build_user_vectors(self, users_data: list[dict]) -> np.ndarray:
        """Create feature vectors from user reading data.

        Each dict in users_data should have:
            user_id, genre_counts (dict[str, int]), total_books,
            avg_speed, avg_rating, avg_session_minutes
        Returns (n_users, n_features) array.
        """
        vectors = []
        self.user_ids = []

        for u in users_data:
            self.user_ids.append(u["user_id"])

            # Genre distribution (normalized)
            total_books = max(u.get("total_books", 0), 1)
            genre_counts = u.get("genre_counts", {})
            genre_dist = [genre_counts.get(g, 0) / total_books for g in GENRES]

            vec = genre_dist + [
                float(u.get("avg_speed", 200)),
                float(u.get("avg_rating", 3.0)),
                float(total_books),
                float(u.get("avg_session_minutes", 15)),
            ]
            vectors.append(vec)

        self.user_vectors = np.array(vectors)
        return self.user_vectors

    def train(self, user_vectors: np.ndarray | None = None) -> dict:
        """Train KMeans, finding optimal k via silhouette score."""
        if user_vectors is not None:
            self.user_vectors = user_vectors

        if self.user_vectors is None or len(self.user_vectors) < 6:
            logger.warning("Not enough users (%s) for clustering",
                           len(self.user_vectors) if self.user_vectors is not None else 0)
            return {"error": "not_enough_data"}

        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(self.user_vectors)

        # Find optimal k (3 to min(8, n_users-1))
        max_k = min(8, len(X_scaled) - 1)
        min_k = min(3, max_k)
        best_k = min_k
        best_score = -1.0

        for k in range(min_k, max_k + 1):
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(X_scaled)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(X_scaled, labels)
            if score > best_score:
                best_score = score
                best_k = k

        # Train with best k
        self.kmeans = KMeans(n_clusters=best_k, n_init=10, random_state=42)
        self.labels = self.kmeans.fit_predict(X_scaled)
        self.k = best_k

        # t-SNE for visualization
        perplexity = min(30, len(X_scaled) - 1)
        if perplexity < 2:
            perplexity = 2
        tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42)
        self.tsne_coords = tsne.fit_transform(X_scaled)

        # Save
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "kmeans": self.kmeans,
                "scaler": self.scaler,
                "user_ids": self.user_ids,
                "user_vectors": self.user_vectors,
                "labels": self.labels,
                "tsne_coords": self.tsne_coords,
                "k": self.k,
            },
            MODEL_PATH,
        )
        logger.info("Clustering: k=%d, silhouette=%.3f, %d users", best_k, best_score, len(X_scaled))

        return {
            "k": best_k,
            "silhouette_score": float(best_score),
            "n_users": len(X_scaled),
        }

    def get_cluster(self, user_id: int) -> int | None:
        """Return cluster label for user, or None if not clustered."""
        if self.labels is None:
            return None
        try:
            idx = self.user_ids.index(user_id)
            return int(self.labels[idx])
        except ValueError:
            # User not in training data — predict from vector if available
            return None

    def get_similar_users(self, user_id: int, n: int = 5) -> list[int]:
        """Return user IDs in the same cluster."""
        cluster = self.get_cluster(user_id)
        if cluster is None or self.labels is None:
            return []

        same_cluster = [
            self.user_ids[i]
            for i, label in enumerate(self.labels)
            if label == cluster and self.user_ids[i] != user_id
        ]
        return same_cluster[:n]

    def visualize(self) -> dict:
        """Return t-SNE coordinates + labels for frontend chart."""
        if self.tsne_coords is None or self.labels is None:
            return {"points": [], "k": 0}

        points = []
        for i, uid in enumerate(self.user_ids):
            points.append({
                "user_id": uid,
                "x": float(self.tsne_coords[i][0]),
                "y": float(self.tsne_coords[i][1]),
                "cluster": int(self.labels[i]),
            })

        return {"points": points, "k": self.k}

    def load(self) -> bool:
        """Load saved model from disk."""
        if MODEL_PATH.exists():
            try:
                data = joblib.load(MODEL_PATH)
                self.kmeans = data["kmeans"]
                self.scaler = data["scaler"]
                self.user_ids = data["user_ids"]
                self.user_vectors = data["user_vectors"]
                self.labels = data["labels"]
                self.tsne_coords = data["tsne_coords"]
                self.k = data["k"]
                logger.info("Clustering model loaded from %s", MODEL_PATH)
                return True
            except Exception:
                logger.exception("Failed to load clustering model")
        return False
