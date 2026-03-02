# Beer label generator (Stage 1)

This repo generates **mono PDF labels** (58×60 mm) from a public Google Sheets CSV export.

## Primary CSV columns

- `id`
- `название`
- `Страна` (actually city)
- `Тип`
- `Крепость%`
- `Плотность°P`
- `Горечь`

Only `Крепость%`, `Плотность°P`, `Горечь` may be empty.

### Notes
- Extra columns are allowed.
- Rows missing required fields (`id`, `название`/`Наименование`, `Страна`, `Тип`/`beertype`) are skipped.

## Output

- `labels/{id}.pdf`
- `labels/index.json`

## Setup

Create GitHub Actions secrets:
- `SHEETS_CSV_URL` (required)
- `STORE_NAME` (optional; default: `ТЕМНОЕ СВЕТЛОЕ`)
