"""
Carrier-specific keyword filtering.
Applies before AI enrichment to reduce noise and save API quota.

Two-tier matching:
1. Core carrier keywords (names, "aircraft carrier", "Ford-class", etc.)
   — strong signal, count fully
2. Ambiguous abbreviations (PSA, CSG, CVN) — only count when at least
   one core keyword also matches, to prevent false positives
"""
import re
from typing import Optional


def is_carrier_related(item: dict, config: dict) -> tuple[bool, int, list]:
    """
    Check if a news item is aircraft-carrier related.

    Returns:
        (is_match: bool, match_count: int, matched_keywords: list)
    """
    filters = config.get("filters", {})
    carrier_keywords = filters.get("carrier_keywords", [])
    blocked_keywords = filters.get("blocked_keywords", [])
    min_matches = filters.get("min_keyword_matches", 2)
    require_title_match = filters.get("require_title_match", False)
    ambiguous = set(
        kw.upper() for kw in filters.get("ambiguous_abbreviations", ["PSA", "CSG", "CVN"])
    )

    # Text to match against
    title = item.get("name", "").lower()
    summary = item.get("summary", "")
    body = item.get("full_text", "")[:2000]  # first 2k chars of body
    full_text = f"{title}\n{summary}\n{body}".lower()

    if not full_text.strip():
        return False, 0, []

    # --- Pass 1: find all matching keywords ---
    matched_all = []          # all matched keywords
    matched_core = []         # non-ambiguous (strong signal) keywords
    matched_ambig = []        # ambiguous abbreviations

    for kw in carrier_keywords:
        kw_lower = kw.lower()
        if kw_lower in full_text:
            matched_all.append(kw)
            if kw.upper() in ambiguous:
                matched_ambig.append(kw)
            else:
                matched_core.append(kw)

    # --- Pass 2: ambiguous abbreviations only count if core matches exist ---
    # If we only have ambiguous hits and no core keywords, it's likely
    # a false positive (e.g. "PSA" in a personnel article).
    if matched_core:
        effective_matches = len(matched_all)
        effective_keywords = matched_all
    else:
        # No core matches — ambiguous hits don't count
        effective_matches = 0
        effective_keywords = []

    # --- Pass 3: title match requirement ---
    if require_title_match and effective_matches >= min_matches:
        title_has_any = any(kw.lower() in title for kw in carrier_keywords)
        if not title_has_any:
            return False, 0, []

    # --- Pass 4: blocked keyword guard ---
    # If we have only the bare minimum matches and lots of blocked keywords,
    # the article is probably about a different topic that mentions a carrier
    # in passing.
    is_match = effective_matches >= min_matches

    if is_match and effective_matches == min_matches and blocked_keywords:
        blocked_count = sum(1 for kw in blocked_keywords if kw.lower() in full_text)
        # If there are significantly more blocked terms than carrier matches,
        # and the carrier hits are weak (just generic "carrier"), demote.
        generic_only = all(
            m.lower() in ("carrier", "aircraft carrier") for m in effective_keywords
        )
        if blocked_count > effective_matches * 2 and generic_only:
            is_match = False

    return is_match, effective_matches, effective_keywords
