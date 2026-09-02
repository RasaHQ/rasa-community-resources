# Tutorial template

What a tutorial in this catalog **is**, so that many can be built without each
one inventing its own shape.

This is the tutorial-specific companion to
[RESOURCE_TEMPLATE.md](RESOURCE_TEMPLATE.md). That file governs the README of
*any* runnable resource — example, pattern, tutorial, workshop. This one adds
the three things that are true of a tutorial and of nothing else: it spans two
repositories, it opens by showing a failure, and it declares what each step
teaches before the work starts.

Read RESOURCE_TEMPLATE.md first. Everything it says about metadata blocks,
`uv.lock`, and index rows applies here unchanged and is not repeated.

---

## 1. The two-repo contract

A tutorial is not one artifact. It is **two**, in two repositories, and both
halves must land before the tutorial exists.

| Half | Repository | Path |
| --- | --- | --- |
| Runnable project | `RasaHQ/rasa-community-resources` | `tutorials/<project-name>/` |
| Chapter prose | `RasaHQ/rasa-community` | `src/content/tutorials/<slug>/` |

Neither half is optional. Two of the four tutorials that predate this document
ship a runnable project with **no published prose at all** — they are
unfindable by a reader who has not already been told the directory name. A
tutorial without chapters is an example; file it under `examples/` and stop
calling it a tutorial.

### 1a. The runnable half

Same shape as any catalog project. In addition:

- `README.md` with the RESOURCE_TEMPLATE metadata block, and a link to the
  published chapters once they exist.
- `pyproject.toml` pinning `rasa-pro==<RASA_PRO_VERSION>` exactly.
- `.env.example` naming every key the project needs.
- A `Makefile` whose targets a chapter can reference by name (`make env`,
  `make install`, `make train`, `make chat`).

### 1b. The prose half, and its frontmatter

Chapters are Markdown under `src/content/tutorials/<slug>/`:

    index.md          the overview, order 0
    01-<name>.md      chapter 1
    02-<name>.md      chapter 2
    ...

The frontmatter contract is **not a style convention — it is a Zod schema**
enforced at build time in `src/content.config.ts`. A build fails on a field
that is missing, misspelled, or of the wrong type. Verify against that file,
not against this table, if the two ever disagree.

| Field | Required? | Type | Notes |
| --- | --- | --- | --- |
| `title` | **required** | string | Chapters use `'Chapter N — <topic>'`. |
| `description` | **required** | string | One sentence. Becomes the card subtitle and the meta description. |
| `tutorial` | **required** | string | The series slug. **Identical in every file of the series** — this is the join key; a typo silently splits one series into two. |
| `order` | **required** | number | `0` for `index.md`, then 1, 2, 3… Sorting is numeric, not filename order. |
| `companionRepo` | optional | URL | Link to the runnable half. **Treat as required for a tutorial** — it is the only pointer from prose to code. |
| `date` | optional | string | ISO date. Set on `index.md`; the tutorial listing sorts by it, so an overview without one sorts last. |
| `author` | optional | enum | An id from `src/data/authors.ts` — **not a free-text name**. An unlisted id fails the build. Set on `index.md` only; chapters inherit. |

Note the asymmetry: four fields are schema-required, three are schema-optional
but two of those (`companionRepo`, `date`) are required *by this template*
because a tutorial without a code link or a date is worse than one with.

### 1c. The prose half's gates

`npm run build` is **not sufficient**, and the site repo's pre-commit hook is
the real gate. It runs a copy gate, an asset gate, a pin check, a
tutorial-card check, Prettier, ESLint, and `astro check`. Two of those catch
tutorial authors specifically.

**1. The library card is a separate, required file.** Chapters that build are
not chapters that are reachable:

    ✗ series 'guarding-irreversible-actions' has no library card — its pages
      build, but nothing links to them.

Add a `LibraryEntry` to `src/data/content.ts` with
`url: '/library/tutorials/<slug>/'` and `hosted: true`. The check is
bidirectional — every series needs a card and every card needs a series — so
this cannot be done ahead of the prose or left behind after it.

**2. Prettier is a separate job from the build.** Markdown wrapped by hand to
80 columns builds perfectly and fails `format:check`. Write the prose however
you like, then run

    npx prettier --write 'src/content/tutorials/<slug>/*.md' src/data/content.ts

and re-run the build afterwards, because reflowing changes the files.

There is also a **copy gate** that rejects hype vocabulary and exclamation
marks anywhere in content. It is not a style preference you can argue with in
review; it fails the commit.

---

## 2. The opening requirement

**A tutorial opens by SHOWING the failure. It never opens by describing the
feature.**

This is the single most load-bearing rule in this document, because it is the
one a hurried author breaks first and a reviewer can check in ten seconds.

The bar is `session-start-personalization/index.md`. It opens by running the
thing and printing what actually came out:

```text
bot  Hello! What can I assist you with today?
```

then names it in five words — *"Correct, and completely anonymous"* — and
states the missing piece **before proposing anything**.

Three moves, in this order:

1. **Print real output.** Not paraphrased, not idealised. What the terminal
   said.
2. **Name what is wrong with it in one line.** The output is usually not
   broken. It is correct and insufficient, and saying so is the hook.
3. **State the missing piece, then show the end state.** The reader now knows
   what they are buying before they spend an hour.

A first chapter that opens with "In this tutorial you will learn about…" or a
bulleted feature list is **rejected at review**. The flagship
`voice-ai-agent/index.md` opens with `## What you will build` and is the
counter-example, not the model — it predates this rule and is grandfathered,
not endorsed.

"What you will build" is a fine *second* section. It is never the first one.

---

## 3. The declared step list

This is the anti-slop gate. It is the reason this document exists.

**Every tutorial declares its step list before any work starts**, in its
charter and in its README. A reviewer with the register open compares the
proposed list against the lists already in the catalog, and **rejects a list
that is a permutation of an existing one**.

### Steps are named for what they TEACH

    GOOD   step-03-constraints      step-06-composition     step-02-first-tool
    BAD    step-03-banking          step-06-insurance       step-02-hotel

The industry is dressing. Two tutorials in different industries may both need
`step-02-first-tool`, and that is fine and expected. What is not fine is a
tutorial whose **whole list** is an existing list with the nouns swapped —
because whatever it says on the tin, it teaches nothing the catalog does not
already teach.

### The test a reviewer applies

> Strip every industry noun from the proposed list. Strip them from the
> nearest existing list. Are they now the same list?

If yes, the cell is rejected regardless of how different the two agents look
when you talk to them. If no, the cell must be able to say **which steps are
the new ones** and what concept each introduces.

Concretely, a proposed cell states:

- the ordered step list, named by concept;
- for each step, one line on the concept it introduces;
- the nearest existing step list in the catalog, named;
- the steps that differ from it, and why the difference is a concept and not
  a noun.

The last two bullets are the work. A proposal that skips them has not been
reviewed for slop, only for spelling.

### The test, run against the catalog as it stands

This is not hypothetical. Applied to the six voice example projects that carry
step lists, every one of them reduces to the same list:

    examples/mantle-voice-banking-skills      scaffold faq check-balance  tool-constraints block-card    transfer                 remaining
    examples/mantle-voice-telco-skills        scaffold faq check-bill     tool-constraints reset-router  internet                 remaining
    examples/mantle-voice-insurance-skills    scaffold faq view-policies  tool-constraints file-claim    composition              remaining
    examples/mantle-voice-car-purchase-skills scaffold faq check-balance  tool-constraints reserve-car   schedule                 remaining
    examples/mantle-voice-appointment-skills  scaffold faq list-contacts  constraints      book-appt     composition-add-contact  remaining
    tutorials/rasa-voice-agent-tutorial       scaffold faq itinerary      constraints      scoped        baggage/composition      remaining

Strip the industry nouns and all six are:

    scaffold | faq | READ-TOOL | tool-constraints | WRITE-TOOL | SECOND-FLOW | remaining

Six artifacts, one step list, six industries. **The slop this gate exists to
prevent has already happened at a scale of six**, and it happened without
anyone deciding to do it — each author copied the nearest neighbour, which is
the correct thing to do when there is no template and the wrong thing when the
neighbour is itself a copy.

Two consequences for anyone using this document:

1. **Do not use those six as your model.** They are a good agent shape and a
   collapsed teaching shape. Copy their project layout; do not copy their step
   list.
2. **A reviewer now has a concrete baseline.** Any proposal reducing to the
   seven-step list above is rejected on sight, because the catalog teaches it
   six times already.

### When your cell builds on an existing artifact

Most cells will compose a pattern rather than start from nothing, and that is
where a step list quietly re-teaches something. State, in the README, in one
short section:

- **which artifact you compose**, by path;
- **the question it answers**, in one sentence;
- **the question yours answers**, in one sentence, phrased so the two do not
  overlap;
- what you take as an **input** and therefore do not teach.

If you cannot write those four lines without the last two sounding the same,
you are rebuilding the pattern with different nouns and the cell should be
rejected.

Worked example, from the first tutorial built against this template:

> `patterns/voice-auth-stepup` answers *how strong is this caller's
> verification, and how do they raise it?* This tutorial answers *given a tier,
> is this particular action allowed?* Tier is an input here, not the subject.

There is **no cross-project import mechanism** in this repository. Composition
means the reader clones both and the prose links them; it does not mean a
shared package. Do not invent one — say so in your charter if you need one.

### Chapters and steps

Chapter numbers and step names are allowed to differ — a step may take two
chapters to explain, and a chapter may cover two cheap steps. But the step
list is the spine, and every step appears in some chapter. If a declared step
never shows up in the prose, either the step was decoration or the prose has a
hole.

---

## 4. The step-snippet machinery: OPTIONAL

Seven projects in this catalog carry `tutorial/snippets/step-NN-<name>/`
directories plus a `TAGS.md` of git recovery tags:

    examples/mantle-voice-agent                 examples/mantle-voice-insurance-skills
    examples/mantle-voice-appointment-skills    examples/mantle-voice-telco-skills
    examples/mantle-voice-banking-skills        tutorials/rasa-voice-agent-tutorial
    examples/mantle-voice-car-purchase-skills

Count them before deciding it is a niche convention. It is the repository's
**dominant** convention among voice projects — and it is still **not
mandatory**, for the cost reasons below.

Use it when: the tutorial will be *presented live*, and a presenter needs to
jump forward or recover mid-session. That is what the machinery is for —
`TAGS.md` is explicitly a presenter's escape hatch, not a reader's aid.

Skip it when: the tutorial is read, not performed.

Know the cost before you choose. Measured on the projects that carry it, the
snippet tree is **31–51% of all files in the project**, and the snippets are
**not copies of the finished code** — they are deliberate intermediate states
(step-02's skill is the pre-constraints version that step-03 then upgrades).
That means they cannot be generated from the finished project, and **nothing
in `lint_repo.py` checks that they still correspond to it.** A snippet tree is
a second copy of the project that drifts silently.

If you use it, say so in the README and keep the step directory names
identical to the declared step list.

### The cost, measured

The first tutorial built against this template **did not** use the machinery.
That was a decision, and here is the arithmetic behind it.

Measured on the three largest projects that carry it:

| Project | Step dirs | Snippet files | Snippet lines | Snippets as share of project files |
| --- | --- | --- | --- | --- |
| `examples/mantle-voice-telco-skills` | 7 | 45 | 1,735 | **51%** |
| `tutorials/rasa-voice-agent-tutorial` | 8 | 38 | 1,330 | **46%** |
| `examples/mantle-voice-banking-skills` | 7 | 34 | 1,622 | **31%** |

Roughly **five files and ~200 lines per step**, and between a third and half of
everything in the directory.

The number is not the argument, though. Two properties are:

1. **Snippets are not derivable from the finished project.** Spot-checked
   `step-02-check-balance/skill.md` against the shipped
   `skills/check_balance/skill.md`: they differ substantively, and correctly —
   the snippet is the pre-constraints version that step-03 then upgrades. So
   they cannot be generated, and a generator (RULING-011 approach C) does not
   remove this cost.
2. **Nothing checks them.** `grep -c snippet scripts/lint_repo.py` returns 0.
   No gate verifies a snippet still corresponds to the project it teaches. It
   is a second copy of the codebase with no consistency check, which is the
   textbook shape of documentation that silently goes stale.

**Recommendation: keep it optional, and make the decision per tutorial on
whether the material will be presented live.** Mandating it across many cells
buys a presenter feature for readers who are not presenters, at a third to a
half of every project's file count, unverified. If it is ever mandated, the
same PR must add a lint check that snippets still parse and still differ from
the finished project in only the intended direction — otherwise the mandate
produces stale directories at scale rather than teaching material.

---

## 5. Catalog laws already in force

These are not new. They are enforced by `scripts/lint_repo.py` and
`make validate`, and they are listed here so a tutorial author does not have to
discover them by failing CI.

- **Fixture data only.** Seeded demo identities under `data/source/`. No real
  customer data, ever, including in transcripts pasted into chapters.
- **`.env.example` completeness.** Every key the project reads is named there,
  and every key declared in `[tool.rasa-catalog] required-secrets` appears in
  it. Enforced by `check_env_examples`.
- **The pin matches `RASA_PRO_VERSION`.** `pyproject.toml`, `uv.lock`, and the
  README `Verified with:` line all say the same version. Enforced by
  `check_version_consistency` and `check_lock_sync`.
- **No real credentials.** No keys, licences, or JWTs in tracked files; no
  tracked `.env`. Enforced by `check_secret_hygiene`.
- **Top-level keys are top-level.** `rules:`, `name:`, `description:` in
  `agent.yml` are siblings of `agent:`, not children. Nested, they parse
  cleanly and are silently discarded. Enforced by `check_agent_config_keys`.
- **An escalation boundary is stated for every T3 use case.** A tutorial whose
  agent handles a high-risk flow says, in prose and in the skill, what it will
  **not** do and where the caller goes instead. "Offer a human" is a
  behaviour; write it down as one.

### Not yet: eval suites

**Do not ship `rasa test e2e` or dialogue-understanding tests with a tutorial
cell.** Verified against installed `3.20.0.dev6`: `mantle/processor.py:104-107`
hardcodes `is_calm_assistant = True`, so the `ensure_calm_only_bot` gate in
`cli/dialogue_understanding_test.py:185-199` passes — while
`grep -c dialogue_understanding mantle/orchestration/orchestrator.py` returns
**0**. DU tests execute, pass, and measure a component that never runs on
Mantle. A green suite here is not evidence.

This section is a hold, not a permanent ban. It lifts when the harness is
retargeted onto the engine's own simulation doctrine.

### Instead: ship a proof of the thing you actually claimed

The hold above says what not to ship. It does not excuse shipping nothing, and
building the first tutorial against this template showed why the gap matters:
the claim a good tutorial makes is usually **not** a claim about the model.

If your tutorial's point is "this function refuses X", that is a claim about a
Python function, and it is provable by calling the function. Ship a script —
`make policy`, `make prove`, whatever names it — that:

- runs with **no licence, no API key, and no network**;
- exercises the guarantee including the failure branches and the malformed
  input;
- prints what it refused and why, in the same words the chapters use;
- exits non-zero when a case does not behave as documented.

This is stronger than a conversation test for this class of claim, not a
substitute for one. A conversation test says the usual path is usually taken.
A direct call says the unusual path is closed — and stays true when the model
changes.

Two things to know before you write one. First, it doubles as the tutorial's
opening: the printed refusals are real output, which is exactly what section 2
demands and what authors otherwise have to stage by hand. Second, **write the
assertions before you trust them.** The first run of the first such script
caught a disagreement between the script and the guard — and the guard was
right, the assertion was wrong. A proof script that has never failed has not
been tested either.

---

## 6. Checklist before you open the PR

Runnable half:

- [ ] `python3 scripts/lint_repo.py` passes
- [ ] `make validate` passes
- [ ] `README.md` carries the RESOURCE_TEMPLATE metadata block
- [ ] `tutorials/README.md` has a row for the new directory
- [ ] `.env.example` names every key
- [ ] no `rasa test e2e` / DU suite

Prose half:

- [ ] `index.md` opens by showing real failing output, not a feature list
- [ ] every file carries `title`, `description`, `tutorial`, `order`
- [ ] `tutorial` is byte-identical across every file in the series
- [ ] `index.md` has `order: 0`, `date`, `companionRepo`, and an `author` id
      that exists in `src/data/authors.ts`
- [ ] a `LibraryEntry` for the series exists in `src/data/content.ts`
- [ ] `npm run build` passes
- [ ] `npx prettier --write` has been run over the chapters AND `content.ts`
- [ ] `npm run format:check`, `npm run lint`, and `astro check` pass
- [ ] no hype vocabulary or exclamation marks (the copy gate rejects them)
- [ ] every declared step appears in some chapter

Both:

- [ ] the declared step list is in the README, and is not a permutation of an
      existing one
- [ ] `companionRepo` points at the runnable half; the README points back
