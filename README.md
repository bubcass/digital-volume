# Edition Mode PoC (PDF-matched)

This PoC renders an Akoma Ntoso XML debate record into a **print-matched** HTML page that looks very close to the current PDF styling (Times New Roman, conservative hierarchy), while remaining accessible and easy to print.

## Run locally

You need to serve the folder (opening `index.html` directly may block `fetch()` for the XML).

### Python
```bash
python -m http.server 8000
```

Open:
- http://localhost:8000

### Node
```bash
npx serve .
```

## Printing

Use your browser's Print dialog. A `@media print` stylesheet:
- removes the grey surround and shadows
- applies page margins
- avoids awkward page breaks around headings/speaker labels

If you provide `data/pagemap.json`, explicit page markers can also be used
to force page breaks in print output (approximate PDF pagination).

## Files

- `index.html` — page template
- `css/styles.css` — PDF-matched styling + print rules
- `js/app.js` — client-side XML → HTML transform
- `data/biden.xml` — sample source XML (swap with any Akoma Ntoso XML using the same structure)
- `data/pagemap.json` — optional sidecar mapping `{page, eid}` for PDF-style page markers
