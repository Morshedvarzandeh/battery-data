# Submitting a datasheet

You have a PDF. You want its numbers in the database, with their conditions
and their page numbers, without typing 40 rows by hand — and you want to see
what was extracted before it counts.

That is this flow. **Extraction produces a proposal; a human accepts, edits or
rejects it.** Nothing reaches the database on a model's say-so.

---

## The short version

1. Open an issue with the **Submit a datasheet** template.
2. Opening the issue records the request but spends no API credit.
3. A repository owner manually starts one extraction and explicitly approves
   that paid call. The workflow opens a pull request with every value, its
   conditions and the quote it came from.
4. **Merge** to accept. **Edit the branch** to modify. **Close** to reject.

The pull request *is* the review step. There is no separate approval UI to
build or log into, and the schema's `review_state` means the same thing on
the database side: `pending_review` until a person says otherwise.

---

## What gets checked before you ever see it

The extractor validates its own output against the same schema CI enforces,
and fails rather than filing something that looks confident and is wrong.

**Conditions.** Fifty-one of the ninety-eight quantities are meaningless
without them. A capacity with no rate and no cutoff is not a fact — the same
cell differs by several percent between 0.2C and 1C. The extraction prompt
forbids guessing, and requires the model to *name* what the document leaves
out:

```yaml
conditions:
  temperature_c: 25
  unstated: [rate_value, rate_unit, voltage_lower_v]
```

That is a correct extraction. Silently omitting them, or quietly assuming
25 °C, is refused:

```
observations[0] (capacity): missing required condition 'rate_value'.
Supply it, or if the source does not state it, add 'rate_value' to
conditions.unstated -- do not omit it.
```

**Evidence.** Every observation carries a page number and a verbatim quote.
No quote, no observation.

**Deployment claims.** If the document names real end uses, they land in
`applications` with an `attribution_basis`. Anything short of a first-hand
document — a teardown, a trade article, an inference — must also state a
confidence:

```
applications[0]: basis 'teardown' is indirect evidence, so 'confidence' is
required. State how sure you are -- an unhedged teardown claim reads like a
manufacturer statement.
```

---

## What to actually look at in the review

Two failure modes account for nearly all of them:

1. **A quote that does not say what its value claims.** The number is right
   there on the page, but attached to the neighbouring column, or to a
   different model in a shared comparison table. Datasheet tables interleave
   badly, and a row of four cells followed by a row of four masses is exactly
   where pairing goes wrong.
2. **A condition marked unstated that is in fact printed.** Often in a
   footnote, a table header, or a "test conditions" block three pages away.

Everything else — a missing quantity, an awkward statistic — is a smaller
problem than either of those, because it is visible. These two are not.

One more, specific to identity: **the manufacturer is who made the cell, not
who published the document.** A testing laboratory's report is not evidence
that the laboratory built the cell, and several well-known datasets carry the
lab's own sample designations rather than manufacturer part numbers.

---

## Running it yourself

No GitHub involved:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python tools/extract_datasheet.py --pdf cell.pdf \
    --manufacturer "Samsung SDI" --model INR21700-50E --kind cell
```

Add `--dry-run` to print the YAML instead of writing it. Output lands in
`contrib/cells/<manufacturer>/<model>.yaml`; `--out` overrides.

`--redistributable` is off by default and should usually stay off. The
repository then keeps the extracted facts plus a URL, a hash and a retrieval
date, never the document body — which keeps a takedown request a per-source
problem rather than a project-ending one. See `source.redistributable` in the
schema.

---

## The literature miner

The other way work arrives. `agents/literature-miner` searches OpenAlex,
Zenodo and arXiv, triages abstracts for extractable battery data, and files a
ranked shortlist as an issue every Monday.

```bash
# Discovery needs no API key at all — try this first.
python agents/literature-miner/pipeline.py discover --limit 20 --out found.json

# Triage does.
export ANTHROPIC_API_KEY=sk-ant-...
python agents/literature-miner/pipeline.py triage found.json --min-priority 0.6 --allow-paid-api
```

Or run it from the **Actions** tab → *literature-miner* → *Run workflow*.

The miner deliberately stops at a shortlist. It does not extract and it does
not write to the database; a human picks what is worth the extraction cost.
That is the design, not a gap.

Models are picked per stage and are overridable:
`MINER_MODEL` for triage volume, `MINER_EXTRACT_MODEL` for extraction, where
a mistake costs reviewer time and can survive into the database.

---

## One-time setup

Paid triage or extraction needs an Anthropic API key as a **repository
secret** — repository admin only, and it cannot be set from a pull request:

> Settings → Secrets and variables → Actions → New repository secret
> Name: `ANTHROPIC_API_KEY`  ·  Value: `sk-ant-...`

Without it, discovery still runs; paid triage and extraction stop with a
message saying exactly this rather than failing obscurely.

A stored key alone cannot trigger spending. Extraction requires a manual
workflow dispatch and its explicit `allow_paid_api` checkbox. Scheduled mining
is discovery-only; paid triage has the same manual opt-in boundary.
