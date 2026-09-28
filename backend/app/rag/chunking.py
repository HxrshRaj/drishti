from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    heading: str


def chunk_markdown(text: str, target_words: int = 120, overlap_words: int = 20) -> list[Chunk]:
    """Split a markdown SOP into chunks along '## ' section boundaries first
    (so a chunk never straddles two unrelated rules), then sub-split any
    section still longer than target_words with a sliding word window.
    """
    # strip YAML frontmatter
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)

    sections: list[tuple[str, str]] = []
    current_heading = "intro"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line.removeprefix("## ").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    chunks: list[Chunk] = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        words = body.split()
        if len(words) <= target_words:
            chunks.append(Chunk(text=f"{heading}: {body}", heading=heading))
            continue
        step = max(target_words - overlap_words, 1)
        for start in range(0, len(words), step):
            piece = " ".join(words[start:start + target_words])
            if piece:
                chunks.append(Chunk(text=f"{heading}: {piece}", heading=heading))
            if start + target_words >= len(words):
                break
    return chunks
