"""Fuzzy catalog search with tag support.

Scoring (higher = better match):
  4 — exact id or name match (case-insensitive)
  3 — name/id starts with query token
  2 — query token is a substring of name/description
  1 — tag match
  0 — no match (excluded)

Tag syntax: prefix a word with ``tag:`` to require a tag match for that token.
Example: ``"tag:healer bags"`` → tag "healer" AND fuzzy "bags".
"""

from __future__ import annotations


def _tok(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _score(entry: dict, tokens: list[str], tag_tokens: list[str]) -> int:
    name  = entry.get("name", "").lower()
    eid   = entry.get("id", "").lower()
    desc  = entry.get("description", "").lower()
    tags  = [t.lower() for t in entry.get("tags", [])]
    ntok  = _tok(name)
    idtok = _tok(eid)

    # Tag filters are mandatory — any miss → exclude
    for tt in tag_tokens:
        if not any(tt in t for t in tags):
            return 0

    if not tokens:
        return 4  # no free-text filter → always include

    best = 0
    for q in tokens:
        qt = _tok(q)
        if not qt:
            continue
        # Exact
        if qt in (ntok, idtok):
            return 4
        # Prefix
        if ntok.startswith(qt) or idtok.startswith(qt) or name.startswith(q):
            best = max(best, 3)
            continue
        # Substring of name/id/desc
        if qt in ntok or qt in idtok or q in desc:
            best = max(best, 2)
            continue
        # No match for this token
        return 0  # all tokens must match

    return best


def search(
    catalog: list[dict],
    query: str,
    category: str = "All",
    only_favorites: bool = False,
    favorites: set[str] | None = None,
) -> list[dict]:
    """Return catalog entries matching *query*, sorted by score then name.

    Each returned entry gets a ``_score`` field (stripped by callers if desired).
    """
    raw = query.strip().lower()
    tag_tokens: list[str] = []
    free_tokens: list[str] = []
    for word in raw.split():
        if word.startswith("tag:"):
            tt = word[4:]
            if tt:
                tag_tokens.append(tt)
        else:
            if word:
                free_tokens.append(word)

    results: list[tuple[int, str, dict]] = []
    for entry in catalog:
        if category != "All" and entry.get("category") != category:
            continue
        if only_favorites and favorites is not None:
            if entry.get("id") not in favorites:
                continue
        sc = _score(entry, free_tokens, tag_tokens)
        if sc == 0 and (free_tokens or tag_tokens):
            continue
        results.append((sc, entry.get("name", "").lower(), entry))

    results.sort(key=lambda t: (-t[0], t[1]))
    return [e for _, _, e in results]
