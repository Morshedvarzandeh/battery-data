# Names before facts: the candidate queue

There are perhaps two hundred companies that make battery cells, another
hundred that make the cathode and anode inside them, and several hundred
factories where the cells are built. Naming them is easy. Proving any one of
them is a different job, and this database only holds things that are proved.

So the two are kept apart. `review/layers/` holds **candidates**: names
recalled without a document, each with the page to check it against.
`contrib/` holds **contributions**: claims with a source, a page and a quote.
Nothing crosses from the first to the second without a document being read.

```
    recalled name                verified against a page              in the library
  review/layers/*.yaml   ->   review/layers/verified/*.yaml   ->   contrib/{companies,sites}/
   no source at all          source + url + sha256 + quote          loaded into bd.*
        |                              |                                    |
   bd_stage.layer_candidate     a person reviews it            tools/load_layers.py
   /v1/layer_candidates                                        /v1/companies, /v1/sites
```

## What a candidate is

A name, a country, a role or a site kind, the page to verify it against, and
how sure the recall is. That is all. A candidate carries **no source, no
page, no quote, no capacity, no tonnage and no price**, and three separate
things enforce that:

| Gate | What it refuses |
|---|---|
| `json-schema/layer-candidate.schema.json` | `additionalProperties: false`, so a `quote`, a `source` or a `capacity_gwh` is not even a valid field |
| `tools/validate_layer_candidates.py` | any key named like provenance, anywhere in the file, however nested |
| `bd_stage.layer_candidate`'s CHECK | a row whose payload carries a quote, page, locator or source |

The last one is the one that matters, because it holds even if a file is
loaded by something other than the tool:

```sql
INSERT INTO bd_stage.layer_candidate (..., payload)
VALUES (..., '{"quote": "invented"}');
-- ERROR: new row violates check constraint "candidate_carries_no_provenance"
```

A candidate also declares its own uncertainty. `confidence` is `high` for a
company or plant that is widely reported and stable, `medium` where a detail
may be off, `low` where the existence or the current status genuinely needs
checking. Every set carries a `caveat` naming what it is, and a `recalled_on`
date, because a recall ages: **plant status is the field most likely to be
wrong**, and the sets say so.

## The sets

| Set | Companies | Sites |
|---|---|---|
| `cell-makers` | cell, primary-battery and storage-battery makers worldwide, from CATL and LG to the lead-acid and supercapacitor makers | |
| `active-material-makers` | cathode, anode, precursor, electrolyte, separator and foil makers | their cathode, anode, electrolyte and separator plants |
| `gigafactories` | the joint ventures and car makers that operate cell plants | cell, module and pack factories |
| `upstream-and-recycling` | miners, refiners, recyclers, second-life companies, test laboratories and certification bodies | mines, brine operations, refineries, recycling plants and test laboratories |

Counts and the breakdown by stage and country:

```bash
python tools/validate_layer_candidates.py --stats
```

## Verifying one

`tools/verify_layer_candidates.py` fetches the page a candidate names, turns
it into text, finds the company's or the site's name in it, and writes a
contribution whose source is that page and whose locator quotes the sentence
the name appears in:

```bash
python tools/verify_layer_candidates.py --set cell-makers --limit 20
python tools/verify_layer_candidates.py --promote          # write into contrib/ directly
```

What it does and does not claim is the point:

* the **name** rests on the quote, and the source carries the URL, the
  retrieval date and the sha256 of the bytes that were read;
* every **other** field came from the recall, and the record says so in as
  many words: *"Recalled, not yet confirmed by a document"*. A reviewer sees
  exactly what is evidence and what is still a guess;
* a name that is **not** on the page produces nothing. It is logged in
  `review/layers/verification-log.json` and stays in the queue.

Getting the quote right takes more care than it looks. A page's `<title>`
and its navigation bar name the company before any prose does, so the tool
turns block-level tags and menu separators into sentence boundaries, then
scores every sentence that names the company and takes the most prose-like
one. The script and style tags are dropped before any of that, so a company
name inside a script can never become a quote.

This needs network access to the companies' own sites. Offline,
`--offline-dir` reads saved pages, which is how `tests/test_layer_candidates.py`
exercises the whole path without a network.

## Querying the queue

The work still to be done is as queryable as the work already finished, in
its own API layer that says plainly it is not the library:

```bash
curl -G localhost:8080/v1/layer_candidates \
     --data-urlencode 'filter=kind = "cell_factory" AND country = "DE"'
curl -G localhost:8080/v1/layer_candidates \
     --data-urlencode 'filter=stages HAS "active_material" AND confidence = "high"'
```

Every response carries `"accepted": false` and a warning in its metadata.
`in_library` says whether the uid already names something the library holds,
so a candidate that has been verified and promoted stops looking like work.

On the Coverage tab of the page, a target the queue names shows in a third
colour, **named, awaiting a document**, between *sourced, with quotes* and
*not covered*. The distinction is the whole point of this layer: knowing what
to look for is not the same as knowing it.

## Why the names are here at all

A reasonable objection is that a list of recalled names does not belong in a
provenance-first database. The answer is that it is not in the database: it
is in staging, behind a constraint that refuses provenance, in an API layer
labelled not-accepted, and in a directory called `review`. What it buys is a
work order with 500 entries and a URL each, instead of a blank page. The
alternative was not a better list; it was no list.
