from __future__ import annotations

import os
from pathlib import Path


class Settings:
    data_images_dir: Path = Path(os.environ.get("DATA_IMAGES_DIR", "../data/images"))
    data_labels_file: Path = Path(os.environ.get("DATA_LABELS_FILE", "../data/labels/labels.jsonl"))
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = int(os.environ.get("PORT", "8100"))


settings = Settings()
