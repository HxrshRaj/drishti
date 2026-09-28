from __future__ import annotations

import re
from pathlib import Path

from app.config import settings
from app.rag.chunking import chunk_markdown
from app.vectorstore.embeddings import EMBEDDING_DIM, embed_texts
from app.vectorstore.factory import get_vector_store

SOPS_COLLECTION = "drishti_sops"

_FRONTMATTER_ID_RE = re.compile(r"^id:\s*(\S+)", re.MULTILINE)
_FRONTMATTER_TITLE_RE = re.compile(r"^title:\s*(.+)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[str, str]:
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    fm = fm_match.group(1) if fm_match else ""
    doc_id = (_FRONTMATTER_ID_RE.search(fm) or [None, "unknown"])[1] if fm_match else "unknown"
    title_m = _FRONTMATTER_TITLE_RE.search(fm)
    title = title_m.group(1).strip() if title_m else doc_id
    return doc_id, title


def ingest_sops(sops_dir: Path | None = None) -> int:
    """Chunks and embeds every SOP markdown file, upserts into the vector
    store. Returns the number of chunks ingested. Idempotent: re-running
    upserts the same deterministic chunk ids.
    """
    sops_dir = sops_dir or settings.data_sops_dir
    store = get_vector_store()
    store.ensure_collection(SOPS_COLLECTION, dim=EMBEDDING_DIM)

    files = sorted(Path(sops_dir).glob("*.md"))
    all_ids, all_texts, all_metas = [], [], []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        doc_id, title = _parse_frontmatter(raw)
        chunks = chunk_markdown(raw)
        for i, chunk in enumerate(chunks):
            all_ids.append(f"{doc_id}::chunk-{i}")
            all_texts.append(chunk.text)
            all_metas.append({"doc_id": doc_id, "title": title, "heading": chunk.heading,
                               "source_file": path.name, "kind": "sop"})

    if not all_ids:
        return 0

    vectors = embed_texts(all_texts)
    store.upsert(SOPS_COLLECTION, all_ids, vectors, all_texts, all_metas)
    return len(all_ids)


if __name__ == "__main__":
    n = ingest_sops()
    print(f"Ingested {n} SOP chunks into collection {SOPS_COLLECTION!r}")
