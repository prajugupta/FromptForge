def should_rollback(best_score: float, new_score: float, margin: float = 0.03) -> bool:
    return new_score < (best_score - margin)
