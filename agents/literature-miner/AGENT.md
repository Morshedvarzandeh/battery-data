# Literature Miner

An agent that finds battery papers and datasets, works out what extractable
data they actually contain, reverse-engineers it into structured records, and
files those records into the review queue with provenance tight enough that a
human can verify any single value in about ten seconds.

The last clause is the whole design constraint. An LLM reading a paper produces
fluent, plausible, and sometimes wrong output, and no amount of prompt care
removes that. What removes it is making every claim cheap to check: a page, a
table, a bounding box, a quoted sentence. So the agent's job is not "extract
values" — it is "extract values *together with the evidence that would let
someone reject them*."

---

## Pipeline

```
  DISCOVER ─→ TRIAGE ─→ ACQUIRE ─→ CLASSIFY ─→ EXTRACT ─→ VALIDATE ─→ QUEUE
     │           │          │          │           │           │         │
   search     is there    get the   what kind   pull the    check it   human
   sources    data here?  full text  of data?   numbers     mechanically review
```

Each stage is a separate model call with a narrow job. This matters: a single
mega-prompt that "reads the paper and returns the data" hallucinates far more
than a chain where each step has one decision to make and can answer "no".

---

## 1. DISCOVER

Sources, in rough order of yield per unit of effort:

| Source | API | What it gives |
|---|---|---|
| Crossref | `api.crossref.org/works` | DOI, title, abstract, license, funder |
| OpenAlex | `api.openalex.org/works` | Full-text search, concepts, open-access links |
| arXiv | `export.arxiv.org/api/query` | Preprints, full PDF, cond-mat/physics.chem-ph |
| Semantic Scholar | `api.semanticscholar.org/graph/v1` | Citation graph, TLDR, open PDFs |
| Zenodo | `zenodo.org/api/records` | **Datasets** — highest value per record |
| Figshare | `api.figshare.com/v2/articles/search` | Datasets, supplementary files |
| OSTI | `www.osti.gov/api/v1/records` | US national-lab reports (INL, NREL, SNL, ANL) |
| Materials Data Facility | `api.materialsdatafacility.org` | Battery datasets |
| BatteryArchive | `batteryarchive.org/data/` | Curated cycling data, per-cell CSVs |
| GitHub | code search | Analysis repos that embed data |
| Unpaywall | `api.unpaywall.org` | Legal open-access copy of a paywalled DOI |

Query strategy is **multi-modal**, because a single phrasing misses most of the
corpus. Run these in parallel and union the results:

- **By test method** — "hybrid pulse power characterization", "HPPC", "EIS
  lithium-ion aging", "GITT diffusion coefficient", "incremental capacity
  analysis", "differential voltage analysis", "accelerating rate calorimetry"
- **By cell identity** — "INR21700", "18650 NMC", "LG M50", "A123 ANR26650",
  "Kokam SLPB", "LFP prismatic 280Ah"
- **By quantity** — "entropic coefficient", "specific heat capacity lithium
  cell", "thermal conductivity pouch cell anisotropic", "self-discharge rate"
- **By dataset intent** — "battery cycling dataset", "open data degradation",
  "data descriptor battery" (targets *Scientific Data* and *Data in Brief*,
  which are unusually high-yield)
- **By degradation mode** — "loss of lithium inventory", "knee point", "calendar
  aging Arrhenius", "lithium plating onset"

Deduplicate on DOI, then on normalised title, then on PDF content hash. Record
every query and its result count in `agent_run.input_summary` so that coverage
is measurable rather than assumed.

## 2. TRIAGE

Cheap model, abstract only, one question: **does this contain extractable
battery data, and of what kind?**

```json
{
  "has_data": true,
  "data_kinds": ["cycle_life", "eis", "hppc"],
  "cell_identified": true,
  "cell_hint": "LG INR21700-M50T",
  "data_availability": "supplementary",
  "n_cells_hint": 24,
  "priority": 0.85,
  "reason": "Aging study, 24 cells, RPT every 50 cycles, SI states data on Zenodo"
}
```

`data_availability` drives everything downstream and is ranked:

1. `repository` — a linked Zenodo/Figshare/GitHub dataset. **Parse the files.**
   This is the only path that yields raw time series.
2. `supplementary` — SI tables or CSVs attached to the paper.
3. `tables` — numbers in the paper's own tables.
4. `figures_only` — the data exists solely as plotted curves. Digitisation
   territory (§5).
5. `none` — modelling or review paper. Drop, but record the decision so the
   same DOI is not re-triaged next run.

## 3. ACQUIRE

Respect licensing and robots. Prefer, in order: publisher open-access API,
Unpaywall-resolved copy, arXiv, institutional repository. Never bypass a
paywall. Store `content_sha256`, `license`, `redistributable` on `bd.source`;
if `redistributable` is false, keep the derived facts and the locator, not the
document body.

Chase the links the paper points at — this is where the real data is:

- Data availability statements → Zenodo/Figshare DOIs
- Supplementary files → CSV, XLSX, ZIP archives
- GitHub URLs in the text → often the actual cycler exports
- Cross-references to previously published datasets

## 4. CLASSIFY

Vision model over rendered pages. Build a page map before extracting anything:

```json
{
  "pages": [
    {"page": 4, "regions": [
      {"kind": "table", "bbox": [72,180,540,420], "caption": "Table 2. Cell specifications"},
      {"kind": "figure", "bbox": [72,450,540,700], "caption": "Fig. 3. Capacity fade",
       "plot_type": "xy_line", "n_series": 4, "digitisable": true}
    ]}
  ]
}
```

This exists so extraction can be **scoped to a region**. Asking a model for "the
capacity" of a whole paper invites it to synthesise one. Asking for "the value
in row 3, column 2 of the table in this bounding box" does not.

## 5. EXTRACT

Three extractors, chosen by region kind.

### 5a. Tables → records

Deterministic parse first (`camelot`, `pdfplumber`, `tabula`), model only to
interpret headers and units. The model's job is mapping, not reading numbers —
transcription is what OCR and table parsers are for, and they do not hallucinate.

Every emitted record must carry the conditions. A capacity with no rate,
temperature and cutoff is rejected by `bd_stage.validate_candidate()` before a
human ever sees it, so the extractor is prompted to hunt the conditions down —
they are usually in the caption, the methods section, or a footnote rather than
the table itself.

### 5b. Repository files → test runs

This is the highest-value path and it is mostly plumbing, not inference.

| Format | Parser |
|---|---|
| Arbin `.res` | `galvani`, `cellpy` |
| Arbin `.csv`/`.h5` | native |
| Maccor `.txt`/`.csv` | `maccorcyclingdata`, BEEP conversion schemas |
| Neware `.nda`/`.ndax` | `NewareNDA`, `fastnda` |
| BioLogic `.mpr`/`.mpt` | `galvani`, `eclabfiles`, `yadg` |
| Novonix | `preparenovonix`, BEEP |
| BasyTec / Digatron / Landt / Bitrode / PEC | `battery-data-standard`, DATTES |
| BDF `.bdf.csv` / `.bdf.parquet` | `batterydf` |

Normalise to the BDF column names in `bd.timeseries_record`, and record the
conventions rather than assuming them:

- `current_sign` — **do not guess**. Infer from the data (does capacity
  accumulate while current is positive?) and cross-check against the parser's
  documented default. `battdat`/VDF/BDS are charge-positive; `ionworksdata` is
  discharge-positive. Same column name, opposite meaning.
- `capacity_accum` — Arbin accumulates within a step, Neware gives net per step,
  Voltaiq resets per cycle.
- `cycle_definition` — store the vendor's `cycle_index_as_reported` **and**
  recompute `cycle_index_derived` with a named algorithm.
- `c_rate_reference_capacity_ah` — find what the authors meant by "1C". If they
  never say, mark it unstated. Nameplate and measured C1 routinely differ by
  more than 10%.

Then **segment the run**. Detect the RPT interleaving pattern and write
`bd.test_segment` rows: an aging campaign is `[aging, RPT, aging, RPT, ...]` and
the persistent confusion in the literature about whether a plotted capacity is
the RPT value or the cycling value exists precisely because nobody records this.

Heuristic that works well: RPTs are the low-rate, longer-duration cycles that
recur at a fixed interval. Cluster cycles by (rate, duration, step pattern);
the minority cluster appearing at regular intervals is the RPT.

### 5c. Figures → digitised curves

Only when the data exists nowhere else. Always lower-trust.

1. Crop to the plot region from the page map.
2. Detect axes, tick labels, and log/linear scale (vision model).
3. Trace each series by colour/marker clustering (`WebPlotDigitizer`-style
   algorithm, or `plotdigitizer`).
4. Map pixels → data coordinates via the calibrated axes.
5. **Sanity-check against any stated values.** If the paper's text says "capacity
   faded to 80% after 800 cycles", the digitised curve must agree at that point.
   Disagreement fails the extraction rather than producing a plausible curve.

Emit as `bd.curve` with `evidence = 'plot_digitised'`, the axis calibration in
`processing`, and a bounding box in `source_location`. Digitised points are
never promoted to `accepted` without human review — enforced by the
`agent_values_need_review` constraint on `bd.provenance`.

## 6. VALIDATE

Mechanical, before any human sees it. `bd_stage.validate_candidate()` checks:

- a locator exists (quote, page, or section) — no evidence, no record
- the quantity is known
- every `required_conditions` entry is present or explicitly `unstated`
- the unit is convertible
- the SI value is physically plausible — this catches the single most common
  LLM failure, the mAh/Ah scale error
- confidence floor

Then `bd_stage.detect_conflicts()` compares against accepted data. A candidate
that contradicts an existing value by more than 2% is not an error — it is the
most interesting thing the agent produced that day, and it goes to the top of
the review queue.

## 7. QUEUE

`bd_stage.review_queue` orders by expected review value: conflicts first, then
validation warnings, then low confidence, then quantities with thin coverage.
Reviewer decisions land in `bd_stage.review_action`, and
`bd_stage.agent_accuracy` turns those into a per-prompt-version scoreboard. If a
prompt change makes extraction worse, that is where it shows up — and if
`mean_conf_rejected` drifts up towards `mean_conf_accepted`, the confidence
signal has stopped being informative and the whole prioritisation is running
blind.

---

## Rules the agent operates under

1. **No value without a locator.** Not a soft preference; the insert fails.
2. **No condition without a source.** If the paper does not state the
   temperature, say so via `unstated`. Do not infer 25 °C because it is usual.
3. **Never convert between incommensurable units.** mV/day self-discharge does
   not become µA. A 0.5P rating does not become a C-rate. An AC impedance does
   not become a DC resistance.
4. **Never merge statistics.** "Rated", "typical" and "minimum" capacity are
   three claims, not three estimates of one claim.
5. **Prefer refusing to guessing.** A skipped field costs one missing row; a
   confabulated field costs trust in every row.
6. **Record the negative result.** A paper triaged as having no data is written
   back so the next run does not re-read it.
7. **Respect licences.** Facts are extractable; documents are not necessarily
   redistributable. `source.redistributable` governs whether the body is stored.

---

## Files

- `pipeline.py` — orchestration, stages 1–7
- `prompts/` — one prompt per stage, versioned; hash recorded in `agent_run`
- `parsers/` — cycler-format adapters
- `digitize.py` — figure digitisation
- `schemas/` — JSON Schemas the model is constrained to emit

---

## Where this runs

The agent is ordinary code in this repository - it is not something you
install into Claude. It runs in two places:

**1. Scheduled, in GitHub Actions** (`.github/workflows/mine.yml`) - the
default. Every Monday it searches OpenAlex/Zenodo/arXiv, triages every
abstract with the API, and opens a GitHub issue listing the ranked
candidates. One-time setup: add `ANTHROPIC_API_KEY` as a repository secret
(repo Settings -> Secrets and variables -> Actions).

**2. On your machine, for one-offs:**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python agents/literature-miner/pipeline.py discover --family dataset_intent --out found.json
python agents/literature-miner/pipeline.py triage found.json --out shortlist.json
```

`llm_anthropic.py` is the model adapter: dependency-free (urllib only), and
it FORCES structured output by defining a tool whose input schema is the
stage's JSON Schema and setting `tool_choice` - the API validates the shape,
rather than the pipeline parsing prose and hoping.

## What is running today vs designed

| Stage | Status |
|---|---|
| discover (OpenAlex, Zenodo, arXiv, OSTI) | code complete |
| triage (LLM over abstracts) | code complete, offline-tested |
| acquire / page-map / table extraction | prompts and schemas defined; PDF plumbing to write |
| cycler-file ingestion | complete (`tools/cyclers.py`), tested |
| figure digitisation | designed only (see section 5c) |
| validation + review queue | complete in the database, tested |

The deliberate gap: **nothing this agent produces enters `bd.*` on its own.**
Extracted values land in `bd_stage.candidate`, are validated mechanically,
and wait for a human. The database constraint `agent_values_need_review`
makes this impossible to bypass, not just discouraged.
