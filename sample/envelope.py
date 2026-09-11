"""The canonical document envelope (illustrative).

Every scraper, whatever the portal, stores each project or agent in the same
shape so the exporter, dashboard and emails never special-case a state. Two
ideas are worth taking away:

  1. The envelope separates the RAW layers (list row and detail page, exactly as
     the portal served them) from a NORMALISED layer with a uniform field set.
     Raw-first means a parser fix can re-normalise from stored raw data in
     seconds instead of re-scraping the portal.

  2. The upsert is MERGE-SAFE: a re-run never blanks a field that already has a
     good value, and the unique id comes from immutable source coordinates, not
     from anything the parser produced. That is what makes weekly re-runs safe
     and idempotent.

No database credentials here; this is a shape and a pattern, not the live code.
"""

from __future__ import annotations

from datetime import datetime, timezone


def make_document(unique_id: str, state: str, entity_type: str,
                  source_url: str, list_data: dict, detail_data: dict,
                  normalized_data: dict) -> dict:
    """Assemble one canonical record. Same key order for every state and type."""
    return {
        "unique_id": unique_id,        # from immutable source coordinates only
        "state": state,                # e.g. "karnataka"
        "entity_type": entity_type,    # "project" | "agent"
        "scraped_at": datetime.now(timezone.utc),
        "source_url": source_url,
        "list_data": list_data,        # the listing row, verbatim
        "detail_data": detail_data,    # the detail page, verbatim
        "normalized_data": normalized_data,   # uniform 37/38-field schema
    }


def _prefer_existing(existing: dict, incoming: dict) -> dict:
    """Merge two normalised layers so a blank never overwrites a real value.

    A failed or partial re-fetch must not erase good data captured earlier, so
    for each field the incoming value wins only if it is non-empty; otherwise the
    existing value is kept.
    """
    merged = dict(existing)
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue                    # do not overwrite with a blank
        merged[key] = value
    return merged


def merge_safe_upsert(collection, doc: dict) -> str:
    """Insert or update on the stable unique id, without ever losing good data.

    Illustrative: `collection` is a pymongo-like collection. The unique index on
    unique_id guarantees a re-run updates the same record instead of inserting a
    duplicate.
    """
    existing = collection.find_one({"unique_id": doc["unique_id"]})
    if existing is None:
        collection.insert_one(doc)
        return "inserted"

    doc["normalized_data"] = _prefer_existing(
        existing.get("normalized_data", {}), doc.get("normalized_data", {})
    )
    # detail_data is written with dotted keys in the real code so partial detail
    # merges rather than replacing; kept simple here.
    collection.update_one({"unique_id": doc["unique_id"]}, {"$set": doc})
    return "updated"
