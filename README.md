# Beer label generator (Stage 1)

Generates mono PDF labels (58×60 mm) from a public Google Sheets CSV export.

## Required columns (others ignored)
- `id`
- `название`
- `Страна` (city)
- `Тип`

## Optional columns
- `Крепость%`
- `Плотность°P`
- `Горечь IBU` (preferred) or `Горечь` (fallback)

Rows missing required fields are skipped (useful when your CSV has technical/service rows).
