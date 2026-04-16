"""
fuzzy_match.py — Fuzzy-match a user query against a dict of known app names.

Uses rapidfuzz for fast, accurate matching. Threshold and max results are
read from config.
"""

import logging
from typing import Any

from rapidfuzz import process, fuzz  # type: ignore

from config import FUZZY_MATCH_THRESHOLD, MAX_FUZZY_RESULTS  # type: ignore

logger = logging.getLogger(__name__)


def fuzzy_find(
    user_query: str,
    apps_dict: dict[str, str],
    threshold: float | None = None,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """Return top N app matches for *user_query* above *threshold*.

    Args:
        user_query:  The raw string from the user (e.g. "spotifi").
        apps_dict:   Mapping of display_name → exe_path.
        threshold:   Minimum similarity score (0–100). Defaults to
                     ``FUZZY_MATCH_THRESHOLD * 100``.
        max_results: Maximum number of results. Defaults to ``MAX_FUZZY_RESULTS``.

    Returns:
        List of dicts with keys ``name``, ``path``, ``score``, ordered by
        descending score.
    """
    if not user_query or not apps_dict:
        return []

    score_threshold = (threshold if threshold is not None else FUZZY_MATCH_THRESHOLD) * 100
    limit = max_results if max_results is not None else MAX_FUZZY_RESULTS

    try:
        raw: list[tuple[str, float, Any]] = process.extract(
            user_query.lower(),
            list(apps_dict.keys()),
            scorer=fuzz.WRatio,
            limit=limit * 3,  # over-fetch then filter
        )
    except Exception as e:
        logger.error("fuzzy_match: rapidfuzz error: %s", e)
        return []

    results: list[dict[str, Any]] = []
    for name, score, _ in raw:
        if score >= score_threshold:
            results.append(
                {
                    "name": name,
                    "path": apps_dict[name],
                    "score": round(score, 1),
                }
            )
        if len(results) >= limit:
            break

    logger.debug("fuzzy_match: %d results for query=%r", len(results), user_query)
    return results
