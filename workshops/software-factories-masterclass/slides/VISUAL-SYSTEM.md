# Revised workshop presentation

The 16-slide deck uses the Rasa brand repository's Ink #181210, Cream #FAF6F0, Pink #E85A91, bright panel #FFFBF5 and the supplied official horizontal Ink logo. Newsreader, Inter and JetBrains Mono are the documented open fallback families. Their licences remain in FONT-LICENSES.txt. No proprietary font binary is added.

Edit slides.json for content and presenter notes; run `node build-deck.mjs` to rebuild index.html. The self-contained template.html carries the embedded fonts, exact logo asset, styles and keyboard navigation. workshop.css is a readable copy of the styling. The original slide source and HTML are in archive/2026-10-22-original/slides.

The revised composition is 1600 × 900 and scales to fit the screen. One principal claim per slide, concrete examples, 66 px headings and mostly 24–28 px body text. Sparse diagrams and comparison tables explain relationships.

Maintainers only: attendees use the prebuilt `index.html` and PDF in their codespace and run none of this. To run the deck check, use `PLAYWRIGHT_MODULE=<path to playwright-core> DECK_QA_OUT=<report file> node check-revised.mjs`. It checks text bounds, horizontal overflow, offline loading, keyboard navigation and notes at 1600 × 900 and 1280 × 720, and rebuilds `masterclass-slides.pdf`. Keep the report outside the repository.

Source: https://github.com/RasaHQ/brand . Checked 22 October 2026. This presentation is an adaptation of the brand system, not a supplied corporate template.
