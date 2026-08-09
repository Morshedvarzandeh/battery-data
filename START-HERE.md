# Start here

You have an archive called `battery-data.tar.gz`. Here is what to do with it.

---

## Step 1 — Put it in your repo

```bash
tar xzf battery-data.tar.gz -C /tmp
cd ~/wherever/your/battery-data          # your existing clone of the GitHub repo
cp -r /tmp/battery-data/. .
```

This overwrites your current `README.md` and `LICENSE`. That is intended — the
new versions are the real ones.

## Step 2 — Run one command

```bash
./setup.sh
```

That is the whole thing. It checks what you have installed, creates the
database, loads the schema, loads the example cells, runs every test, and tells
you what worked. It changes nothing outside the database it creates, and it is
safe to run twice.

If you would rather not install Postgres at all:

```bash
docker compose up
```

Same result, nothing installed on your machine, and the API comes up on
<http://localhost:8080/v1/cells>.

## Step 3 — Push it

```bash
git add -A
git commit -m "Schema, cycler adapters, read API, standards crosswalk"
git push
```

---

## Then read exactly two files

**`docs/02-conventions.md`** — the actual thinking. Twenty-seven places where
battery practice contradicts itself, and what this schema does about each one.
These are enforced as database constraints, not written down as advice, so if
you disagree with any of them that is the conversation worth having before there
is data in the system.

**`crosswalk/CROSSWALK.md`** — the piece with value outside your repo. Nobody has
published a mapping between BDF, BattINFO, BPX and the EU Battery Passport. This
is one. Putting it on Zenodo for a DOI takes ten minutes and makes it citable.

Everything else is reference material. Read it when you need it.

---

## What each folder is for

| Folder | You touch this when |
|---|---|
| `schema/` | changing what the database can store |
| `seed/` | adding reference cells by hand |
| `contrib/` | adding cells as versioned YAML (CI checks them) |
| `tools/` | ingesting cycler files, validating, exporting |
| `api/` | serving the data over HTTP |
| `agents/` | mining papers and datasets |
| `docs/` | understanding why something is the way it is |
| `crosswalk/` | **generated** — do not edit, run `tools/export_crosswalk.py` |

---

## Adding your first real cell

Copy `contrib/cells/samsung-sdi/inr21700-50e.yaml`, edit it, then:

```bash
python tools/validate_contrib.py contrib/
python tools/load_contrib.py --dsn dbname=batterydb   # once it is accepted
```

It will refuse a capacity that has no rate, temperature and cutoff voltage. That
refusal is the product. Everything else in this repository exists to make that
one rule enforceable at scale.

---

## One rule to keep

Do not commit manufacturer datasheet PDFs. Store the extracted facts plus a URL,
a hash and a retrieval date — the schema already has fields for all three, and
`source.redistributable` controls whether a document body may be stored. Kept
this way, a takedown request is a per-source problem rather than a project-ending
one.
