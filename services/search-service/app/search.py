"""Searching the index: PostgreSQL full-text search, or a simple fallback (SQLite in tests).

Every word typed must match (as a word prefix, so "comp eng" finds Computer
Engineering). Titles count more than summaries, summaries more than body text.
"""

import re

from sqlalchemy import and_, case, func, literal, or_, select

from .models import CFG, SEARCH_VECTOR, Document

WORD_RE = re.compile(r"\w+", re.UNICODE)
MARK = ("\u2068", "\u2069")  # invisible markers around matched words; the page turns them into <mark>


def words(q: str) -> list[str]:
    return WORD_RE.findall((q or "").lower())[:8]


def search(session, q: str, kind: str | None = None, limit: int = 20, offset: int = 0):
    terms = words(q)
    if not terms:
        return [], 0
    if session.bind.dialect.name == "postgresql":
        query = func.to_tsquery(CFG, " & ".join(f"{t}:*" for t in terms))
        rank = func.ts_rank_cd(SEARCH_VECTOR, query)
        snippet = func.ts_headline(CFG, func.coalesce(Document.summary, "").op("||")(literal(" ")).op("||")(Document.body), query,
                                   f"StartSel={MARK[0]}, StopSel={MARK[1]}, MaxWords=28, MinWords=12, MaxFragments=1")
        where = SEARCH_VECTOR.op("@@")(query)
    else:
        text = func.lower(Document.title + " " + Document.summary + " " + Document.body)
        where = and_(*[text.like(f"%{t}%") for t in terms])
        rank = case((or_(*[func.lower(Document.title).like(f"%{t}%") for t in terms]), 1000), else_=0) - func.length(Document.title)
        snippet = Document.summary
    stmt = select(Document, snippet.label("snippet")).where(where)
    if kind:
        stmt = stmt.where(Document.kind == kind)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.execute(stmt.order_by(rank.desc(), Document.title).limit(limit).offset(offset)).all()
    return rows, total


def kinds(session, q: str) -> dict:
    """How many results of each kind, for the filter chips."""
    terms = words(q)
    if not terms:
        return {}
    rows, _ = search(session, q, limit=1000)
    counts: dict[str, int] = {}
    for doc, _snippet in rows:
        counts[doc.kind] = counts.get(doc.kind, 0) + 1
    return counts
