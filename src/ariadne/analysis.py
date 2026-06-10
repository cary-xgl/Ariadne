from __future__ import annotations

from dataclasses import dataclass

from ariadne.text import normalize_text


@dataclass(frozen=True)
class AnalysisResult:
    model_name: str
    summary: str
    topics: list[str]
    tags: list[str]
    importance_score: float
    novelty_score: float
    recommended_action: str
    reason: str
    raw_output: dict[str, object]


KEYWORDS = {
    "ai": ["ai", "llm", "model", "openai", "人工智能", "模型"],
    "product": ["product", "workflow", "用户", "产品"],
    "engineering": ["python", "docker", "api", "database", "工程", "架构"],
}


def analyze_item(title: str, content: str) -> AnalysisResult:
    text = normalize_text(f"{title} {content}").lower()
    topics = [topic for topic, words in KEYWORDS.items() if any(word in text for word in words)]
    tags = topics.copy() or ["general"]
    importance = min(0.95, 0.35 + 0.15 * len(topics) + min(len(text) / 3000, 0.25))
    novelty = 0.5 if topics else 0.35
    action = "read_now" if importance >= 0.65 else "digest"
    summary_source = normalize_text(content) or normalize_text(title)
    summary = summary_source[:240] + ("..." if len(summary_source) > 240 else "")
    reason = "Matched active interest topics." if topics else "No strong topic match; keep for digest review."
    return AnalysisResult(
        model_name="local-heuristic-v1",
        summary=summary,
        topics=topics,
        tags=tags,
        importance_score=round(importance, 3),
        novelty_score=round(novelty, 3),
        recommended_action=action,
        reason=reason,
        raw_output={"analyzer": "local heuristic", "matched_topics": topics},
    )
