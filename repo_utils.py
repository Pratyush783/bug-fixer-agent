from __future__ import annotations

import os
from typing import List, Tuple


def list_files(root_dir: str, exts: Tuple[str, ...] = (".py",)) -> List[str]:
    out: List[str] = []
    for base, _, files in os.walk(root_dir):
        for fn in files:
            if fn.endswith(exts):
                out.append(os.path.join(base, fn))
    return out


def search_in_repo(root_dir: str, needle: str, exts: Tuple[str, ...] = (".py",)) -> List[str]:
    needle_l = needle.lower()
    hits: List[str] = []
    for fp in list_files(root_dir, exts=exts):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                if needle_l in f.read().lower():
                    hits.append(fp)
        except Exception:
            continue
    return hits
