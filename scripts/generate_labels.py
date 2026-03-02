#!/usr/bin/env python3
"""
Generate 58x60mm mono PDF labels from a public Google Sheets CSV export.

Primary CSV headers (surrounding spaces are ignored):
- id
- название
- Страна              (actually city)
- Тип
- Крепость%
- Плотность°P
- Горечь

The script is tolerant to extra columns and "service" rows.
If a row lacks required fields (id, name, city, type) it is skipped.

Optional fallback headers (if primary is empty/missing):
- name:     Наименование
- type:     beertype
- abv:      крепость
- density:  плотность
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

# Layout Y positions (from top, in mm)
Y_ID = 4.5 * mm
Y_NAME = 13.5 * mm
Y_CITY_TYPE = 22.5 * mm
Y_STATS = 34.0 * mm
Y_STORE = 55.5 * mm

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

    header_map: Dict[str, str] = {normalize_header(h): h for h in reader.fieldnames}

    if "id" not in header_map:
        die(f"Missing required column: 'id'. Found headers: {list(header_map.keys())}")

    def get_from_row(row: Dict[str, str], candidates: List[str]) -> str:
        for cand in candidates:
            if cand in header_map:
                raw_key = header_map[cand]
                val = (row.get(raw_key) or "").strip()
                if val:
                    return val
        return ""

    items: List[Item] = []
    skipped = 0

    for row in reader:
        if not any((v or "").strip() for v in row.values()):
            continue

        item_id = get_from_row(row, ["id"])
        name = get_from_row(row, ["название", "Наименование"])
        city = get_from_row(row, ["Страна"])
        beer_type = get_from_row(row, ["Тип", "beertype"])

        abv = get_from_row(row, ["Крепость%", "крепость"])
        density = get_from_row(row, ["Плотность°P", "плотность"])
        ibu = get_from_row(row, ["Горечь"])

        # Skip service rows that are not products
        if not (item_id and name and city and beer_type):
            skipped += 1
            continue

        items.append(Item(
            id=item_id,
            name=name,
            city=city,
            beer_type=beer_type,
            abv=abv,
            density=density,
            ibu=ibu,
        ))

    if not items:
        die("No valid product rows found (all rows were empty or missing id/name/city/type).")

    if skipped:
        warn(f"Skipped {skipped} non-product/service row(s) that lacked required fields.")

    return items


def clear_labels_dir() -> None:
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    for p in LABELS_DIR.iterdir():
        if p.is_file() and (p.suffix.lower() == ".pdf" or p.name == "index.json"):
            p.unlink()


def draw_label(c: canvas.Canvas, item: Item, store_name: str) -> None:
    def y_from_top(mm_from_top: float) -> float:
        return PAGE_H - mm_from_top

    c.setFillGray(0)

    c.setFont("DejaVu", FS_ID)
    c.drawCentredString(PAGE_W / 2, y_from_top(Y_ID), item.id)

    max_w = PAGE_W - 2 * MARGIN_X
    fs_name = fit_font_size_single_line(item.name, "DejaVu-Bold", FS_NAME_MAX, FS_NAME_MIN, max_w)
    c.setFont("DejaVu-Bold", fs_name)
    c.drawCentredString(PAGE_W / 2, y_from_top(Y_NAME), item.name)

    c.setFont("DejaVu", FS_CITY_TYPE)
    c.drawString(MARGIN_X, y_from_top(Y_CITY_TYPE), item.city)
    c.drawRightString(PAGE_W - MARGIN_X, y_from_top(Y_CITY_TYPE), item.beer_type)

    c.setFont("DejaVu", FS_STATS)
    col_centers = [PAGE_W * (1/6), PAGE_W * (3/6), PAGE_W * (5/6)]
    for x, val in zip(col_centers, [item.abv, item.density, item.ibu]):
        if val:
            c.drawCentredString(x, y_from_top(Y_STATS), val)

    c.setFont("DejaVu-Bold", FS_STORE)
    c.drawCentredString(PAGE_W / 2, y_from_top(Y_STORE), store_name.upper())


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

        index.append({
            "id": item.id,
            "name": item.name,
            "city": item.city,
            "type": item.beer_type,
            "pdf": f"labels/{filename}",
        })

    (LABELS_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Generated {len(items)} labels into {LABELS_DIR}")


def main() -> None:
    url = os.environ.get("SHEETS_CSV_URL", "").strip()
    if not url:
        die("SHEETS_CSV_URL env var is required (public CSV export URL).")

    store_name = (os.environ.get("STORE_NAME") or STORE_DEFAULT).strip() or STORE_DEFAULT

    register_fonts()
    csv_text = fetch_csv(url)
    items = parse_items(csv_text)
    generate_pdfs(items, store_name=store_name)


if __name__ == "__main__":
    main()
