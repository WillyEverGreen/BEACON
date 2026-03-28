# chunk.py
import re, tiktoken

enc = tiktoken.get_encoding("cl100k_base")
CHUNK_MAX = 400
OVERLAP = 40

def token_len(text):
    return len(enc.encode(text))

def chunk_document(text: str, meta: dict) -> list[dict]:
    sections = re.split(r'\n(?=#{1,4} |\b[A-Z][^\n]{0,60}\n[-=]+)', text)
    chunks = []

    for section in sections:
        tokens = enc.encode(section.strip())
        if not tokens:
            continue
        if len(tokens) <= CHUNK_MAX:
            chunks.append({"text": enc.decode(tokens), **meta})
        else:
            start = 0
            while start < len(tokens):
                end = min(start + CHUNK_MAX, len(tokens))
                chunks.append({"text": enc.decode(tokens[start:end]), **meta})
                start += CHUNK_MAX - OVERLAP

    return [c for c in chunks if c["text"].strip()]
