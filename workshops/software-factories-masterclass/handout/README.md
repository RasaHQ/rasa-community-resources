# Printed setup sheet

`rasa-travel-workshop-one-pager.pdf` is a one-page US Letter handout that walks a participant from nothing to their first result: three keys, three GitHub secrets, the Codespace, `bash desk doctor`, and `bash desk data fx USD GBP 200`. A band above the Join bar points to the Rasa Mantle credits page (`rasa.community/mantle-credits/`); its award terms must match that page. `one-pager-preview.png` is a phone-sized preview.

- `one-pager.html` is the source, laid out from the Rasa brand repository: the supplied horizontal Ink logo, cream ground, STK Bureau Serif, Sans and Sans Mono, dark pink links, the Soundwave pattern as a quiet edge band.
- `make-qr.mjs` writes `qr.svg` for the Codespaces launch link, which opens the workshop only once this edition is on `main`.
- `build-one-pager.mjs` renders the PDF and preview with Playwright. It stages the logo, pattern and licensed fonts from outside this repository (`BRAND_ROOT`, `FONT_DIR`); no font file is stored here. The PDF embeds subsets of the fonts, as the font licence ruling allows.

The steps follow sections A to D of the [workshop README](../README.md). Change both together.
