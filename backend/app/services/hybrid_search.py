"""
hybrid_search.py — Local implementation of BM25 sparse retrieval and Reciprocal Rank Fusion (RRF).
Allows combining dense similarity search and keyword matching.
"""
import math
import re
from collections import Counter
from typing import List, Dict, Any


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words."""
    return re.findall(r"\w+", text.lower())


class BM25:
    """Lightweight, self-contained BM25 ranking model for keyword retrieval."""

    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.corpus_size = len(corpus)

        # Pre-tokenize all documents
        self.doc_tokens = [tokenize(doc.get("content", "")) for doc in corpus]
        self.doc_lens = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_len = sum(self.doc_lens) / self.corpus_size if self.corpus_size > 0 else 0

        self.doc_freqs = [Counter(tokens) for tokens in self.doc_tokens]

        # Calculate Document Frequencies (DF)
        self.df = Counter()
        for tokens in self.doc_tokens:
            for term in set(tokens):
                self.df[term] += 1

        # Calculate Inverse Document Frequency (IDF)
        self.idf = {}
        for term, freq in self.df.items():
            # Standard Lucene / BM25 IDF formulation with smoothing
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def get_scores(self, query: str) -> List[float]:
        """Compute BM25 scores for all documents in the corpus given a query."""
        query_tokens = tokenize(query)
        scores = []
        for i in range(self.corpus_size):
            score = 0.0
            doc_len = self.doc_lens[i]
            freqs = self.doc_freqs[i]
            for term in query_tokens:
                if term in freqs:
                    tf = freqs[term]
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                    score += self.idf.get(term, 0.0) * (tf * (self.k1 + 1.0)) / denom
            scores.append(score)
        return scores


def rrf_merge(
    dense_results: List[Dict[str, Any]],
    sparse_results: List[Dict[str, Any]],
    top_k: int = 5,
    k: int = 60,
) -> List[Dict[str, Any]]:
    """
    Merge dense similarity search results and sparse keyword search results
    using Reciprocal Rank Fusion (RRF).

    Both input lists should be pre-sorted by their respective relevance scores descending.
    Returns a merged list of items, sorted by RRF score descending.
    """
    rrf_scores = {}
    doc_map = {}

    def process_list(results):
        for rank, item in enumerate(results, 1):
            chunk_id = item.get("chunk_id")
            if not chunk_id:
                continue
            if chunk_id not in doc_map:
                doc_map[chunk_id] = item
            # RRF Score formula: sum of 1 / (k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))

    process_list(dense_results)
    process_list(sparse_results)

    # Sort chunk_ids by RRF score in descending order
    sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    merged_results = []
    for chunk_id in sorted_chunk_ids[:top_k]:
        item = doc_map[chunk_id].copy()
        item["rrf_score"] = round(rrf_scores[chunk_id], 6)
        merged_results.append(item)

    return merged_results
