# Printed setup sheet

`rasa-travel-workshop-one-pager.pdf` is a one-page US Letter handout that walks a participant from nothing to their first result: three keys, three GitHub secrets, the Codespace, `bash desk doctor`, and `bash desk data fx USD GBP 200`. `one-pager-preview.png` is a phone-sized preview.

- `one-pager.html` is the source. It uses the brand's ink, cream and pink and the Inter, Newsreader and JetBrains Mono fonts the deck uses (copies in `fonts/`, licences in `fonts/FONT-LICENSES.txt`), and stays readable in black and white.
- `make-qr.mjs` writes `qr.svg` for the Codespaces launch link, which opens the workshop only once this edition is on `main`.
- `build-one-pager.mjs` renders the PDF and preview with Playwright.

The steps follow sections A to D of the [workshop README](../README.md). Change both together.
