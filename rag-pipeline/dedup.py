# dedup.py
import hashlib

def md5(text):
    return hashlib.md5(text.encode()).hexdigest()

def trigrams(text):
    w = text.lower().split()
    return set(zip(w, w[1:], w[2:]))

def jaccard(a, b):
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def dedup(chunks: list[dict], threshold=0.85) -> list[dict]:
    seen = set()
    unique = []
    for i, chunk in enumerate(chunks):
        if i % 2000 == 0:
            print(f"  Dedup processing {i}/{len(chunks)}...")
            
        h = md5(chunk["text"])
        if h in seen:
            continue
        seen.add(h)
        
        tc = trigrams(chunk["text"])
        if not tc:
            continue
            
        len_tc = len(tc)
        
        is_dup = False
        for p in unique[-200:]:
            tp = p.get("_trigrams", set())
            if not tp:
                continue
            intersect = len(tc & tp)
            union = len_tc + len(tp) - intersect
            if intersect / union > threshold:
                is_dup = True
                break
                
        if not is_dup:
            chunk["id"] = h
            chunk["_trigrams"] = tc
            unique.append(chunk)

    for c in unique:
        c.pop("_trigrams", None)
        
    return unique
