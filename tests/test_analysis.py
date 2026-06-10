from ariadne.analysis import analyze_item


def test_analyze_item_detects_interest_topics() -> None:
    result = analyze_item("Python API workflow", "Docker and database architecture for an AI model system.")

    assert result.model_name == "local-heuristic-v1"
    assert "engineering" in result.topics
    assert result.importance_score >= 0.65
    assert result.recommended_action == "read_now"
