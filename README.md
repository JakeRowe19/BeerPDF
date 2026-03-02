# Beer labels (Stage 1 + Stage 2)

## Stage 1
Generates mono PDF labels (58×60mm) into:
- `labels/{id}.pdf`
- `labels/index.json`

## Stage 2 (kiosk UI for 1366×768 touch)
Static UI in `docs/`:
- 3-column grid
- no search / filters
- sorted by numeric `id`
- tap item -> print modal (iframe) + big Print button

The workflow copies generated labels to `docs/labels/` for GitHub Pages.

### Enable GitHub Pages
Settings → Pages:
- Source: Deploy from a branch
- Branch: main
- Folder: /docs

### Secrets
- SHEETS_CSV_URL (required)
- STORE_NAME (optional; default: ТЕМНОЕ СВЕТЛОЕ)


### Last updated
Generator writes `labels/meta.json` with UTC timestamp. UI shows it in header.
