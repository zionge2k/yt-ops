"""Plain-text renderers: TSV and a fixed-width table that respects CJK width."""
from __future__ import annotations

import unicodedata


def display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def _cell(v) -> str:
    return "-" if v is None else str(v)


def tsv(rows: list[dict], cols: list[str]) -> str:
    return "\n".join(["\t".join(cols)] + ["\t".join(_cell(r.get(c)) for c in cols) for r in rows])


def _pad(text: str, width: int, right: bool) -> str:
    gap = " " * (width - display_width(text))
    return gap + text if right else text + gap


def table(rows: list[dict], cols: list[str]) -> str:
    cells = [[_cell(r.get(c)) for c in cols] for r in rows]
    # Numbers right-align; None ("-") follows the other values of its column.
    right = [
        any(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool) for r in rows)
        for c in cols
    ]
    widths = [max([display_width(c)] + [display_width(row[i]) for row in cells]) for i, c in enumerate(cols)]
    def line(vals):
        return "  ".join(_pad(v, widths[i], right[i]) for i, v in enumerate(vals))
    return "\n".join([line(cols), "  ".join("-" * w for w in widths)] + [line(row) for row in cells])
