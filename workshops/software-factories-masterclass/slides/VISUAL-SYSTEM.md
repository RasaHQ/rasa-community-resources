# Masterclass visual system

sow: software-factories-masterclass-SOW-02

The designer supplies `visual-system.css`, `visual-diagrams.mjs` and
`check-layout.mjs`. Rasa-ops owns the slide story and text in the single
offline `index.html`. These source helpers are build-time tools: inline the
CSS and generated SVGs into that file. The final deck needs no module loader,
package install, external font host or network connection.

The composition is a local adaptation of Rasa brand tokens v0.2.0, read from
`RasaHQ/brand` at the supplied checkout. Cream and ink carry the composition;
pink marks the focal action, mint a successful result, and orange a rejected
result. These diagrams are teaching illustrations, not product screenshots.
Use the existing embedded Newsreader, Inter and JetBrains Mono faces and keep
`FONT-LICENSES.txt`. Do not add Bureau binaries. Do not reconstruct the Rasa
logo; retain the supplied master when a logo is used.

## Composition contract

Each `.slide` has a `.crumb` navigation line, one `h1`, and one `.scene`.
The scene holds an SVG from the diagram helpers. At 1920 × 1080 the title is
80 px, navigation 32 px, diagram labels at least 32 px, and the designed scene
1680 × 660 px. All content stays inside a 6% safe area. Dimensions scale
together for 1280 × 720; text is never reduced to fit an overfull slide.

Use one sentence for the title and at most 12 visible instructional words in
the diagram and any body copy combined. Numbers, times, links and step labels
count; persistent breadcrumb navigation does not. Do not hide extra teaching
copy in notes, shrink it, clip it or move it off screen to make the gate pass.
An agenda or live-step instruction that cannot fit must be resolved with the
content owner, preserving the operator's required direction and narrative.

The primitives cover a traveller's disconnected sources and connected answer,
the factory sequence, builder versus protected tests, the two complementary
tools, three decision outcomes, chapter checkpoints, question/choice/briefing,
the eight-part roadmap and a capability hub. Labels are arguments
so the content owner can use the agreed vocabulary. Long labels or additional
nodes need a new measured composition rather than automatic font shrinking.

## Render every slide before updating the preview

Use an already installed Playwright Core; this adds no repository dependency:

```sh
node workshops/software-factories-masterclass/slides/check-layout.mjs \
  --playwright /path/to/installed/playwright-core \
  --deck workshops/software-factories-masterclass/slides/index.html \
  --out /path/to/rehearsal-evidence
```

The gate renders all slides at 1920 × 1080 and 1280 × 720, hashes every
screenshot, records its source hash, and exits nonzero for excessive slide or
word count, small text, thin margins, overlapping text, overflow, failed assets,
network fetches or a visual under half the slide area. The visual measurement
uses visible SVG marks, not an empty SVG container. Fixed deck chrome is also
measured. A background panel can be part of a designed scene; geometry alone
cannot prove that it communicates an idea. Inspect the screenshots and obtain
dt-proofreader's teaching/read-aloud review and Council review independently.

The 55-slide source at PR131 `4537736` is the recorded failure baseline.
The visual-system design review is a component demonstration, not a replacement
story, a completed deck or acceptance of the public preview.

`check-layout-controls.mjs` uses the same `--playwright` and `--out` arguments
to render one valid fixture and deliberately broken typography, margin,
overflow, visual-area, word-count, overlap, list, fixed-chrome and navigation
fixtures. It passes only when the gate rejects the expected defect at both
resolutions. These fixtures prove detection behavior, not the teaching quality
of the finished deck.
