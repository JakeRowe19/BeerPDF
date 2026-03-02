#!/usr/bin/env python3
"""
Generate 58x60mm mono PDF labels from a public Google Sheets CSV export.

Expected CSV headers (case-sensitive, but surrounding spaces are ignored):
- id
- название
- Страна              (actually city)
- Тип
- Крепость%
- Плотность°P
- Горечь

Output:
- labels/{id}.pdf
- labels/index.json

Usage:
  python scripts/generate_labels.py

Env vars:
  SHEETS_CSV_URL   Required. Public CSV URL.
  STORE_NAME       Optional. Default: "ТЕМНОЕ СВЕТЛОЕ"
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


ROOT = Path(__file__).resolve().parents[1]
LABELS_DIR = ROOT / "labels"

# Fonts (present on GitHub Actions ubuntu-latest too)
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PAGE_W = 58 * mm
PAGE_H = 60 * mm

MARGIN_X = 2.2 * mm
MARGIN_TOP = 2.0 * mm
MARGIN_BOTTOM = 2.0 * mm

# Layout Y positions (from top, in mm)
Y_ID = 4.5 * mm
Y_NAME = 13.5 * mm
Y_CITY_TYPE = 22.5 * mm
Y_STATS = 34.0 * mm
Y_STORE = 55.5 * mm  # baseline-ish; close to bottom, with margin

# Font sizes (starting points)
FS_ID = 9
FS_NAME_MAX = 18
FS_NAME_MIN = 10
FS_CITY_TYPE = 9
FS_STATS = 12
FS_STORE = 12

STORE_DEFAULT = "ТЕМНОЕ СВЕТЛОЕ"


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def normalize_header(h: str) -> str:
    # strip surrounding whitespace; collapse internal spaces
    h2 = h.strip()
    h2 = re.sub(r"\s+", " ", h2)
    return h2


def fetch_csv(url: str) -> str:
    req = Request(url, headers={"User-Agent": "github-actions/beer-labels/1.0"})
    with urlopen(req) as resp:
        data = resp.read()
    # handle possible UTF-8 BOM
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8")


def safe_id_to_filename(id_value: str) -> str:
    # We expect numeric-ish ids, but keep it safe.
    s = str(id_value).strip()
    if not s:
        die("Row has empty id; cannot generate filename.")
    # allow digits, letters, dash, underscore. Replace others with underscore.
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    return f"{s}.pdf"


def register_fonts() -> None:
    # If font files are missing (custom runners), fail loudly.
    if not Path(FONT_REG).exists() or not Path(FONT_BOLD).exists():
        die("DejaVuSans fonts not found on this runner. Install fonts-dejavu-core.")
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_REG))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))


def text_width(text: str, font_name: str, font_size: float) -> float:
    return pdfmetrics.stringWidth(text, font_name, font_size)


def fit_font_size_single_line(text: str, font_name: str, max_size: int, min_size: int, max_width: float) -> int:
    size = max_size
    while size > min_size and text_width(text, font_name, size) > max_width:
        size -= 1
    return size


@dataclass
class Item:
    id: str
    name: str
    city: str
    beer_type: str
    abv: str
    density: str
    ibu: str


def parse_items(csv_text: str) -> List[Item]:
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    if reader.fieldnames is None:
        die("CSV has no header row.")
    # Normalize headers map
    header_map: Dict[str, str] = {normalize_header(h): h for h in reader.fieldnames}

    required = ["id", "название", "Страна", "Тип", "Крепость%", "Плотность°P", "Горечь"]
    missing = [r for r in required if r not in header_map]
    if missing:
        die(f"Missing required columns in CSV: {missing}. Found headers: {list(header_map.keys())}")

    items: List[Item] = []
    for row in reader:
        # Skip completely empty rows
        if not any((v or "").strip() for v in row.values()):
            continue

        def get(col_norm: str) -> str:
            raw_key = header_map[col_norm]
            return (row.get(raw_key) or "").strip()

        item = Item(
            id=get("id"),
            name=get("название"),
            city=get("Страна"),
            beer_type=get("Тип"),
            abv=get("Крепость%"),
            density=get("Плотность°P"),
            ibu=get("Горечь"),
        )

        # Hard requirements per your spec:
        if not item.id or not item.name or not item.city or not item.beer_type:
            die(f"Row missing required fields (id/name/city/type). Row: {row}")

        items.append(item)

    return items


def clear_labels_dir() -> None:
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    for p in LABELS_DIR.iterdir():
        if p.is_file() and (p.suffix.lower() == ".pdf" or p.name == "index.json"):
            p.unlink()


def draw_label(c: canvas.Canvas, item: Item, store_name: str) -> None:
    # PDF origin is bottom-left; we use helpers from top.
    def y_from_top(mm_from_top: float) -> float:
        return PAGE_H - mm_from_top

    # ID
    c.setFillGray(0)  # black
    c.setFont("DejaVu", FS_ID)
    c.drawCentredString(PAGE_W / 2, y_from_top(Y_ID), item.id)

    # Name (auto fit)
    max_w = PAGE_W - 2 * MARGIN_X
    fs_name = fit_font_size_single_line(item.name, "DejaVu-Bold", FS_NAME_MAX, FS_NAME_MIN, max_w)
    c.setFont("DejaVu-Bold", fs_name)
    c.drawCentredString(PAGE_W / 2, y_from_top(Y_NAME), item.name)

    # City / Type line
    c.setFont("DejaVu", FS_CITY_TYPE)
    half_w = (PAGE_W - 2 * MARGIN_X) / 2
    # Left: city (left-aligned within left half)
    c.drawString(MARGIN_X, y_from_top(Y_CITY_TYPE), item.city)
    # Right: type (right-aligned within right half)
    c.drawRightString(PAGE_W - MARGIN_X, y_from_top(Y_CITY_TYPE), item.beer_type)

    # Stats (3 columns, centered)
    c.setFont("DejaVu", FS_STATS)
    col_centers = [PAGE_W * (1/6), PAGE_W * (3/6), PAGE_W * (5/6)]
    values = [item.abv, item.density, item.ibu]
    for x, val in zip(col_centers, values):
        if val:
            c.drawCentredString(x, y_from_top(Y_STATS), val)

    # Store name bottom
    c.setFont("DejaVu-Bold", FS_STORE)
    c.drawCentredString(PAGE_W / 2, y_from_top(Y_STORE), store_name.upper())


def generate_pdfs(items: List[Item], store_name: str) -> List[Dict[str, str]]:
    clear_labels_dir()

    index: List[Dict[str, str]] = []
    for item in items:
        filename = safe_id_to_filename(item.id)
        out_path = LABELS_DIR / filename
        c = canvas.Canvas(str(out_path), pagesize=(PAGE_W, PAGE_H))
        draw_label(c, item, store_name=store_name)
        c.showPage()
        c.save()

        index.append({
            "id": item.id,
            "name": item.name,
            "city": item.city,
            "type": item.beer_type,
            "pdf": f"labels/{filename}",
        })

    # Write index.json
    (LABELS_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def main() -> None:
    url = os.environ.get("SHEETS_CSV_URL", "").strip()
    if not url:
        die("SHEETS_CSV_URL env var is required (public CSV export URL).")
    store_name = os.environ.get("STORE_NAME", STORE_DEFAULT).strip() or STORE_DEFAULT

    register_fonts()
    csv_text = fetch_csv(url)
    items = parse_items(csv_text)
    generate_pdfs(items, store_name=store_name)
    print(f"Generated {len(items)} labels into {LABELS_DIR}")


if __name__ == "__main__":
    main()
