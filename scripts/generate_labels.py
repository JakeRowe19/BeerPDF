#!/usr/bin/env python3
"""
Stage 1: Generate 58x60mm mono PDF labels from a public Google Sheets CSV export.

Required columns (others ignored):
- id
- название
- Страна (city)
- Тип

Optional columns:
- Крепость%
- Плотность°P
- плотность (fallback for density)
- Горечь IBU (preferred)
- Горечь (fallback)

Robustness:
- Technical/service columns are ignored.
- Rows missing required fields are skipped.
- Broken formula outputs like '#VALUE!' are treated as empty.
- For density, if 'Плотность°P' contains '%' (e.g. '5,2% 16OG'), we keep only the last token ('16OG').

Dynamic layout:
- Stats row shows only non-empty values (3/2/1 values -> reflow).
- If no stats (e.g., non-alcoholic), the whole label content is vertically centered.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from urllib.request import Request, urlopen

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
LABELS_DIR = ROOT / "labels"

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PAGE_W = 58 * mm
PAGE_H = 60 * mm

MARGIN_X = 2.2 * mm
MARGIN_TOP = 3.0 * mm
MARGIN_BOTTOM = 3.0 * mm

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

def warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)

def normalize_header(h: str) -> str:
    h2 = (h or "").strip()
    h2 = re.sub(r"\s+", " ", h2)
    return h2

def fetch_csv(url: str) -> str:
    req = Request(url, headers={"User-Agent": "github-actions/beer-labels/1.0"})
    with urlopen(req) as resp:
        data = resp.read()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8")

def safe_id_to_filename(id_value: str) -> str:
    s = str(id_value).strip()
    if not s:
        raise ValueError("empty id")
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    return f"{s}.pdf"

def register_fonts() -> None:
    if not Path(FONT_REG).exists() or not Path(FONT_BOLD).exists():
        die("DejaVuSans fonts not found. Install fonts-dejavu-core.")
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_REG))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))

def text_width(text: str, font_name: str, font_size: float) -> float:
    return pdfmetrics.stringWidth(text, font_name, font_size)

def fit_font_size_single_line(text: str, font_name: str, max_size: int, min_size: int, max_width: float) -> int:
    size = max_size
    while size > min_size and text_width(text, font_name, size) > max_width:
        size -= 1
    return size

def is_bad_value(val: str) -> bool:
    v = (val or "").strip()
    if not v:
        return True
    v_up = v.upper()
    if "#VALUE" in v_up:
        return True
    if v in {"-", "—", "–"}:
        return True
    if v_up in {"0", "0%", "0%OG", "0% OG"}:
        return True
    if v_up.replace(" ", "") == "IBU":
        return True
    return False

def clean_density(density_p: str, density_raw: str) -> str:
    dp = (density_p or "").strip()
    dr = (density_raw or "").strip()
    if is_bad_value(dp): dp = ""
    if is_bad_value(dr): dr = ""

    # If dp includes ABV too (has %), keep only last token, e.g. "16OG", "-OG"
    if dp and "%" in dp:
        parts = [p for p in re.split(r"\s+", dp) if p]
        last = parts[-1] if parts else ""
        return "" if is_bad_value(last) else last

    if dp:
        return dp

    if dr:
        if "°" in dr or "OG" in dr.upper():
            return dr
        return f"{dr}°P"
    return ""

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
    header_map: Dict[str, str] = {normalize_header(h): h for h in reader.fieldnames}

    for req in ["id", "название", "Страна", "Тип"]:
        if req not in header_map:
            die(f"Missing required column: '{req}'. Found headers: {list(header_map.keys())}")

    def get(row: Dict[str, str], header: str) -> str:
        if header not in header_map:
            return ""
        return (row.get(header_map[header]) or "").strip()

    items: List[Item] = []
    skipped = 0
    for row in reader:
        if not any((v or "").strip() for v in row.values()):
            continue

        item_id = get(row, "id")
        name = get(row, "название")
        city = get(row, "Страна")
        beer_type = get(row, "Тип")

        if not (item_id and name and city and beer_type):
            skipped += 1
            continue

        abv = get(row, "Крепость%")
        abv = "" if is_bad_value(abv) else abv

        density = clean_density(get(row, "Плотность°P"), get(row, "плотность"))

        ibu = get(row, "Горечь IBU") or get(row, "Горечь")
        ibu = "" if is_bad_value(ibu) else ibu

        items.append(Item(item_id, name, city, beer_type, abv, density, ibu))

    if not items:
        die("No valid product rows found.")
    if skipped:
        warn(f"Skipped {skipped} non-product/service row(s).")
    return items

def clear_labels_dir() -> None:
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    for p in LABELS_DIR.iterdir():
        if p.is_file() and (p.suffix.lower() == ".pdf" or p.name == "index.json"):
            p.unlink()

def line_height(font_size: float) -> float:
    return font_size * 1.25

def draw_label(c: canvas.Canvas, item: Item, store_name: str) -> None:
    c.setFillGray(0)
    max_w = PAGE_W - 2 * MARGIN_X
    fs_name = fit_font_size_single_line(item.name, "DejaVu-Bold", FS_NAME_MAX, FS_NAME_MIN, max_w)

    stats_vals = [v for v in [item.abv, item.density, item.ibu] if (v or "").strip()]
    have_stats = len(stats_vals) > 0

    gaps = {
        "id_name": 2.8 * mm,
        "name_city": 2.6 * mm,
        "city_stats": (3.2 * mm) if have_stats else (2.0 * mm),
        "stats_store": (5.5 * mm) if have_stats else (2.5 * mm),
    }

    h_id = line_height(FS_ID)
    h_name = line_height(fs_name)
    h_city = line_height(FS_CITY_TYPE)
    h_stats = line_height(FS_STATS) if have_stats else 0
    h_store = line_height(FS_STORE)

    total_h = h_id + gaps["id_name"] + h_name + gaps["name_city"] + h_city + gaps["city_stats"] + h_stats + gaps["stats_store"] + h_store
    usable_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
    top_offset = MARGIN_TOP + max(0, (usable_h - total_h) / 2)

    y = PAGE_H - top_offset

    c.setFont("DejaVu", FS_ID)
    c.drawCentredString(PAGE_W / 2, y, item.id)
    y -= h_id + gaps["id_name"]

    c.setFont("DejaVu-Bold", fs_name)
    c.drawCentredString(PAGE_W / 2, y, item.name)
    y -= h_name + gaps["name_city"]

    c.setFont("DejaVu", FS_CITY_TYPE)
    c.drawString(MARGIN_X, y, item.city)
    c.drawRightString(PAGE_W - MARGIN_X, y, item.beer_type)
    y -= h_city + gaps["city_stats"]

    if have_stats:
        c.setFont("DejaVu", FS_STATS)
        n = len(stats_vals)
        if n == 1:
            xs = [PAGE_W / 2]
        elif n == 2:
            xs = [PAGE_W * 0.25, PAGE_W * 0.75]
        else:
            xs = [PAGE_W * (1/6), PAGE_W * (3/6), PAGE_W * (5/6)]
            stats_vals = stats_vals[:3]
        for x, val in zip(xs, stats_vals):
            c.drawCentredString(x, y, val)
        y -= h_stats + gaps["stats_store"]
    else:
        y -= gaps["stats_store"]

    c.setFont("DejaVu-Bold", FS_STORE)
    c.drawCentredString(PAGE_W / 2, y, store_name.upper())

def generate_pdfs(items: List[Item], store_name: str) -> None:
    clear_labels_dir()
    index = []
    for item in items:
        filename = safe_id_to_filename(item.id)
        out_path = LABELS_DIR / filename
        c = canvas.Canvas(str(out_path), pagesize=(PAGE_W, PAGE_H))
        draw_label(c, item, store_name=store_name)
        c.showPage()
        c.save()
        index.append({"id": item.id, "name": item.name, "city": item.city, "type": item.beer_type, "pdf": f"labels/{filename}"})

    (LABELS_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(items)} labels into {LABELS_DIR}")

def main() -> None:
    url = os.environ.get("SHEETS_CSV_URL", "").strip()
    if not url:
        die("SHEETS_CSV_URL env var is required (public CSV export URL).")
    store_name = (os.environ.get("STORE_NAME") or STORE_DEFAULT).strip() or STORE_DEFAULT
    register_fonts()
    items = parse_items(fetch_csv(url))
    generate_pdfs(items, store_name)

if __name__ == "__main__":
    main()
