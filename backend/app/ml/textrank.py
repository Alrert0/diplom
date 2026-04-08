import logging
import re

import networkx as nx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex."""
    # Handle common abbreviations to avoid false splits
    text = re.sub(r"(Mr|Mrs|Dr|Ms|Prof|Sr|Jr|St)\.", r"\1<DOT>", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.replace("<DOT>", ".").strip() for s in sentences]
    # Filter out very short fragments
    sentences = [s for s in sentences if len(s.split()) >= 4]
    return sentences


def extract_key_sentences(text: str, top_n: int = 5) -> list[str]:
    """
    Extract top N key sentences from text using TextRank algorithm.

    Steps:
    1. Split text into sentences
    2. Build TF-IDF vectors for each sentence
    3. Compute cosine similarity matrix
    4. Build graph with networkx
    5. Run PageRank
    6. Return top N sentences in original order
    """
    sentences = _split_sentences(text)

    if len(sentences) <= top_n:
        return sentences

    # Build TF-IDF matrix
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(sentences)
    except ValueError:
        # Can happen if all sentences are stop words
        logger.warning("TF-IDF failed, returning first %d sentences", top_n)
        return sentences[:top_n]

    # Cosine similarity matrix
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Build graph — nodes are sentence indices, edges are similarity weights
    graph = nx.Graph()
    for i in range(len(sentences)):
        graph.add_node(i)

    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            weight = sim_matrix[i][j]
            if weight > 0.05:  # Only add edges with meaningful similarity
                graph.add_edge(i, j, weight=weight)

    # Run PageRank
    try:
        scores = nx.pagerank(graph, weight="weight", max_iter=100)
    except nx.PowerIterationFailedConvergence:
        # Fallback: use degree centrality
        scores = nx.degree_centrality(graph)

    # Get top N sentence indices sorted by score
    ranked_indices = sorted(scores, key=scores.get, reverse=True)[:top_n]

    # Return sentences in original document order
    ranked_indices.sort()
    return [sentences[i] for i in ranked_indices]
