# verify.py
import chromadb

WCAG_22_ALL_SC = [
    # Principle 1 — Perceivable
    "1.1.1",
    "1.2.1","1.2.2","1.2.3","1.2.4","1.2.5","1.2.6","1.2.7","1.2.8","1.2.9",
    "1.3.1","1.3.2","1.3.3","1.3.4","1.3.5","1.3.6",
    "1.4.1","1.4.2","1.4.3","1.4.4","1.4.5","1.4.6","1.4.7","1.4.8","1.4.9",
    "1.4.10","1.4.11","1.4.12","1.4.13",
    # Principle 2 — Operable
    "2.1.1","2.1.2","2.1.3","2.1.4",
    "2.2.1","2.2.2","2.2.3","2.2.4","2.2.5","2.2.6",
    "2.3.1","2.3.2","2.3.3",
    "2.4.1","2.4.2","2.4.3","2.4.4","2.4.5","2.4.6","2.4.7","2.4.8","2.4.9","2.4.10",
    "2.4.11","2.4.12","2.4.13",                         # new in 2.2
    "2.5.1","2.5.2","2.5.3","2.5.4","2.5.5","2.5.6",
    "2.5.7","2.5.8",                                     # new in 2.2
    # Principle 3 — Understandable
    "3.1.1","3.1.2","3.1.3","3.1.4","3.1.5","3.1.6",
    "3.2.1","3.2.2","3.2.3","3.2.4","3.2.5",
    "3.2.6",                                             # new in 2.2
    "3.3.1","3.3.2","3.3.3","3.3.4","3.3.5","3.3.6",
    "3.3.7","3.3.8","3.3.9",                             # new in 2.2
    # Principle 4 — Robust
    # 4.1.1 intentionally excluded — removed/obsolete in WCAG 2.2
    "4.1.2","4.1.3",
]  # 86 total

def verify_coverage():
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_collection("accessibility_kb")
    
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    covered  = set()
    for meta in all_meta:
        for sc in meta.get("wcag_sc","").split(","):
            if sc.strip():
                covered.add(sc.strip())

    missing = [sc for sc in WCAG_22_ALL_SC if sc not in covered]
    print(f"\nWCAG 2.2 coverage: {len(WCAG_22_ALL_SC)-len(missing)}/{len(WCAG_22_ALL_SC)}")
    if missing:
        print(f"Missing SC: {missing}")
        return False
    else:
        print("Full WCAG 2.2 coverage confirmed (86/86).")
        return True

if __name__ == "__main__":
    verify_coverage()
