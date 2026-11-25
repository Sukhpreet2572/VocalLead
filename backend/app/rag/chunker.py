"""Section-aware character chunks with stable content-derived identifiers."""
import hashlib
import re


def normalize(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def chunks(document_id: str, text: str, size: int = 800, overlap: int = 120) -> list[tuple[str, str]]:
    if overlap >= size:
        raise ValueError("Chunk overlap must be less than size")
    result = []
    cleaned = normalize(text)
    for start in range(0, len(cleaned), size - overlap):
        part = cleaned[start:start + size].strip()
        if not part:
            break
        digest = hashlib.sha256(f"{document_id}:{start}:{part}".encode()).hexdigest()[:24]
        result.append((f"{document_id}:{digest}", part))
        if start + size >= len(cleaned):
            break
    return result
