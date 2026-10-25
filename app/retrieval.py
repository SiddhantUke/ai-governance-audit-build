import math
import re
from collections import Counter

RISK_WEIGHT = {"unacceptable": 1.0, "high": 0.7, "limited": 0.4}


def _tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower().replace("_", " "))


def _requirement_text(requirement):
    return " ".join([
        requirement.get("framework", ""),
        requirement.get("clause", ""),
        requirement.get("title", ""),
        requirement.get("obligation", ""),
        requirement.get("control_type", ""),
        requirement.get("evidence_required", ""),
    ])


class RetrievalIndex:
    def __init__(self, requirements):
        self.requirements = requirements
        self.documents = [_tokens(_requirement_text(r)) for r in requirements]
        doc_count = len(self.documents)
        df = Counter()
        for tokens in self.documents:
            for token in set(tokens):
                df[token] += 1
        self.idf = {token: math.log((doc_count + 1) / (count + 1)) + 1 for token, count in df.items()}
        self.vectors = [self._vector(tokens) for tokens in self.documents]

    def _vector(self, tokens):
        counts = Counter(tokens)
        total = len(tokens) or 1
        return {token: (count / total) * self.idf.get(token, 0.0) for token, count in counts.items()}


    def _cosine(self, vec_a, vec_b):
        dot = sum(vec_a.get(token, 0.0) * value for token, value in vec_b.items())
        norm_a = math.sqrt(sum(value * value for value in vec_a.values())) or 1.0
        norm_b = math.sqrt(sum(value * value for value in vec_b.values())) or 1.0
        return dot / (norm_a * norm_b)

    def search(self, query, top_k=5):
        query_tokens = _tokens(query)
        query_set = set(query_tokens)
        query_vec = self._vector(query_tokens)
        candidates = []
        for requirement, doc_tokens, vec in zip(self.requirements, self.documents, self.vectors):
            cosine = self._cosine(query_vec, vec)
            overlap = len(query_set & set(doc_tokens)) / len(query_set) if query_set else 0.0
            hybrid = 0.5 * cosine + 0.5 * overlap
            candidates.append((requirement, hybrid, cosine, overlap))
        candidates.sort(key=lambda item: item[1], reverse=True)
        shortlist = candidates[: max(top_k * 2, top_k)]
        ranked = []
        for rank_before, (requirement, hybrid, cosine, overlap) in enumerate(shortlist, start=1):
            control_words = set(_tokens(requirement.get("control_type", "")))
            control_match = 1.0 if (control_words & query_set) else 0.0
            risk = RISK_WEIGHT.get(requirement.get("risk_tier", "limited"), 0.4)
            rerank_score = round(0.7 * hybrid + 0.2 * risk + 0.1 * control_match, 4)
            ranked.append({
                "requirement_id": requirement.get("id"),
                "framework": requirement.get("framework"),
                "clause": requirement.get("clause"),
                "title": requirement.get("title", ""),
                "obligation": requirement.get("obligation", ""),
                "risk_tier": requirement.get("risk_tier"),
                "control_type": requirement.get("control_type"),
                "stage1_hybrid": round(hybrid, 4),
                "stage1_cosine": round(cosine, 4),
                "stage1_overlap": round(overlap, 4),
                "rank_before_rerank": rank_before,
                "rerank_score": rerank_score,
            })
        ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
        for rank_after, item in enumerate(ranked[:top_k], start=1):
            item["rank_after_rerank"] = rank_after
        return ranked[:top_k]
