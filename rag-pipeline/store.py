# store.py
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="accessibility_kb",
    metadata={"hnsw:space": "cosine"}
)

def store_chunks(chunks: list[dict]):
    if not chunks:
        print("No chunks to store.")
        return
        
    for i in range(0, len(chunks), 100):
        batch = chunks[i:i+100]
        collection.add(
            ids        = [c["id"] for c in batch],
            embeddings = [c["embedding"] for c in batch],
            documents  = [c["text"] for c in batch],
            metadatas  = [{
                "silo":        c.get("silo", ""),
                "severity":    c.get("severity", "unknown"),
                "issue_type":  c.get("issue_type", "general"),
                "wcag_sc":     ",".join(c.get("wcag_sc", [])),
                "user_impact": ",".join(c.get("user_impact", [])),
                "topic":       c.get("topic", ""),
                "url":         c.get("url", ""),
                "token_count": str(c.get("token_count", 0)),
            } for c in batch]
        )
    print(f"Stored {len(chunks)} chunks total.")
