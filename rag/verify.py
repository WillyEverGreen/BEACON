"""
WCAG 2.2 Coverage Verification — checks that the vector store contains
chunks tagged with all 86 WCAG 2.2 success criteria.

Can be run standalone: python verify.py
"""
import logging

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger("rag.verify")

# ── Complete WCAG 2.2 Success Criteria (86 total) ────────────
# 4.1.1 intentionally excluded — removed/obsolete in WCAG 2.2

WCAG_22_ALL_SC: list[str] = [
    # Principle 1 — Perceivable
    "1.1.1",
    "1.2.1", "1.2.2", "1.2.3", "1.2.4", "1.2.5", "1.2.6", "1.2.7", "1.2.8", "1.2.9",
    "1.3.1", "1.3.2", "1.3.3", "1.3.4", "1.3.5", "1.3.6",
    "1.4.1", "1.4.2", "1.4.3", "1.4.4", "1.4.5", "1.4.6", "1.4.7", "1.4.8", "1.4.9",
    "1.4.10", "1.4.11", "1.4.12", "1.4.13",
    # Principle 2 — Operable
    "2.1.1", "2.1.2", "2.1.3", "2.1.4",
    "2.2.1", "2.2.2", "2.2.3", "2.2.4", "2.2.5", "2.2.6",
    "2.3.1", "2.3.2", "2.3.3",
    "2.4.1", "2.4.2", "2.4.3", "2.4.4", "2.4.5", "2.4.6", "2.4.7", "2.4.8", "2.4.9", "2.4.10",
    "2.4.11", "2.4.12", "2.4.13",                         # new in 2.2
    "2.5.1", "2.5.2", "2.5.3", "2.5.4", "2.5.5", "2.5.6",
    "2.5.7", "2.5.8",                                     # new in 2.2
    # Principle 3 — Understandable
    "3.1.1", "3.1.2", "3.1.3", "3.1.4", "3.1.5", "3.1.6",
    "3.2.1", "3.2.2", "3.2.3", "3.2.4", "3.2.5",
    "3.2.6",                                             # new in 2.2
    "3.3.1", "3.3.2", "3.3.3", "3.3.4", "3.3.5", "3.3.6",
    "3.3.7", "3.3.8", "3.3.9",                             # new in 2.2
    # Principle 4 — Robust
    "4.1.2", "4.1.3",
]  # 86 total

CHROMA_PERSIST_DIR: str = "./chroma_db"
CHROMA_COLLECTION: str = "accessibility_kb"


def get_coverage_details() -> dict:
    """
    Collect detailed WCAG coverage stats from the vector store.

    Returns:
        {
            "ok": bool,
            "covered_count": int,
            "total": int,
            "missing": list[str],
            "error": str,
        }
    """
    details = {
        "ok": False,
        "covered_count": 0,
        "total": len(WCAG_22_ALL_SC),
        "missing": list(WCAG_22_ALL_SC),
        "error": "",
    }

    try:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        collection = client.get_collection(CHROMA_COLLECTION)
    except Exception as e:
        details["error"] = f"Cannot connect to ChromaDB: {e}"
        return details

    try:
        all_meta = collection.get(include=["metadatas"])["metadatas"]
    except Exception as e:
        details["error"] = f"Failed to read metadatas: {e}"
        return details

    covered: set[str] = set()
    for meta in all_meta:
        if not isinstance(meta, dict):
            continue
        for sc in str(meta.get("wcag_sc", "")).split(","):
            if sc.strip():
                covered.add(sc.strip())

    missing: list[str] = [sc for sc in WCAG_22_ALL_SC if sc not in covered]
    details["missing"] = missing
    details["covered_count"] = len(WCAG_22_ALL_SC) - len(missing)
    details["ok"] = not missing
    return details


def verify_coverage() -> bool:
    """
    Verify that the vector store covers all 86 WCAG 2.2 success criteria.
    
    Returns:
        True if full coverage (86/86), False otherwise.
        Logs missing SC IDs as warnings.
    """
    details = get_coverage_details()
    if details["error"]:
        logger.error(details["error"])
        return False

    logger.info(f"WCAG 2.2 coverage: {details['covered_count']}/{details['total']}")
    if details["missing"]:
        logger.warning(f"Missing SC: {details['missing']}")
        return False

    logger.info("Full WCAG 2.2 coverage confirmed (86/86).")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    verify_coverage()
