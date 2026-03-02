# Beer label generator (Stage 1)

This repo generates **mono PDF labels** (58×60 mm) from a public Google Sheets CSV export.

## CSV columns (must exist)

- `id`
- `название`
- `Страна` (actually city)
- `Тип`
- `Крепость%`
- `Плотность°P`
- `Горечь`

Only `Крепость%`, `Плотность°P`, `Горечь` may be empty.

## Output

- `labels/{id}.pdf` — one label per product
- `labels/index.json` — metadata list

## Setup

1. Publish your Google Sheet as CSV (public URL).
2. In GitHub repo settings → **Secrets and variables** → **Actions** → create secrets:
   - `SHEETS_CSV_URL` = your CSV export URL
   - (optional) `STORE_NAME` = override store name (default: `ТЕМНОЕ СВЕТЛОЕ`)

3. The workflow runs hourly (and can be run manually).

## Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SHEETS_CSV_URL="https://docs.google.com/spreadsheets/d/.../export?format=csv"
python scripts/generate_labels.py
```
