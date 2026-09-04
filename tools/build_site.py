#!/usr/bin/env python3
"""Render the website: one static page per product, maker and section.

WHY THIS EXISTS
---------------
The site used to be one page that fetched nothing and rendered everything: a
single HTML file carrying all 64 products with their 600 values and 245
quoted sentences, and a router that drew whichever view you asked for. It was
fast to write and wrong in two ways.

It was slow. Reading the home page meant parsing 138 kB of product data the
home page never shows, and the library view built 64 drawings at once, each
with its own set of gradient definitions -- 320 of them on one screen.

And it could not be found. A search engine indexes URLs, and a hash route is
not a URL: `#/p/cell/rept/314ah` is a fragment of the home page. Sixty-four
products, one indexable page between them, and nothing in the HTML for a
crawler that does not run scripts.

So the pages are generated here instead. Every product gets a real URL and a
real page, with its specifications in the HTML before any script runs. Every
page carries only its own data. What the pages share -- the stylesheet, the
drawing code, a small index of the library for search -- they share as three
cached files.

    python tools/build_site.py           # render the site
    python tools/build_site.py --check   # fail if anything is stale (CI)

Everything under web/ except bench.html, sim.js and data/ is generated. Edit
the contribution, the stylesheet, app.js or this file -- never the output.
"""
from __future__ import annotations
import argparse, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_web_data as bd                                   # the data, once

ROOT = bd.ROOT
WEB = os.path.join(ROOT, "web")
REPO = "https://github.com/Morshedvarzandeh/battery-data"

# Where the site will live. Change this line, or set BD_SITE_URL, and every
# canonical link, sitemap entry and social card follows.
SITE_URL = os.environ.get("BD_SITE_URL", "https://morshedvarzandeh.github.io/battery-data").rstrip("/")
BRAND = "battery-data"
TAGLINE = "Specifications, with their conditions"

# --------------------------------------------------------------------------
# The vocabulary the pages speak. Kept beside the renderer that uses it.
# --------------------------------------------------------------------------
KIND = {"cell": "Cell", "primary_cell": "Primary cell", "module": "Module",
        "pack": "Pack", "system": "System"}
KIND_PL = {"cell": "Cells", "primary_cell": "Primary cells", "module": "Modules",
           "pack": "Packs", "system": "Systems"}
FORM = {"cylindrical": "Cylindrical", "prismatic_hardcase": "Prismatic", "prismatic": "Prismatic",
        "pouch": "Pouch", "blade": "Blade", "coin": "Coin", "button": "Button", "other": "Assembled"}
STAT = {"nominal": "nominal", "typical": "typical", "maximum": "maximum", "minimum": "minimum",
        "rated": "rated", "standard": "standard", "absolute_max": "absolute maximum",
        "absolute_min": "absolute minimum"}
UNIT = {"mohm": "mΩ", "ohm": "Ω"}

QNAME = {
    "capacity": "Capacity", "nominal_voltage": "Nominal voltage", "energy": "Energy",
    "usable_energy": "Usable energy", "open_circuit_voltage": "Open-circuit voltage",
    "charge_cutoff_voltage": "Charge cut-off voltage",
    "discharge_cutoff_voltage": "Discharge cut-off voltage",
    "absolute_max_voltage": "Absolute maximum voltage",
    "absolute_min_voltage": "Absolute minimum voltage", "shipping_voltage": "Shipping voltage",
    "specific_energy": "Specific energy", "energy_density": "Energy density",
    "specific_power": "Specific power", "specific_capacity": "Specific capacity",
    "areal_capacity": "Areal capacity",
    "max_continuous_discharge_current": "Continuous discharge current",
    "max_continuous_charge_current": "Continuous charge current",
    "max_pulse_discharge_current": "Pulse discharge current",
    "standard_charge_current": "Standard charge current",
    "cv_cutoff_current": "Constant-voltage cut-off current",
    "peak_power": "Peak power", "rated_power": "Rated power", "power": "Power",
    "internal_resistance_ac": "Internal resistance, AC",
    "internal_resistance_dc": "Internal resistance, DC",
    "ohmic_resistance": "Ohmic resistance", "charge_transfer_resistance": "Charge-transfer resistance",
    "area_specific_impedance": "Area-specific impedance",
    "mass": "Mass", "diameter": "Diameter", "height": "Height", "length": "Length",
    "width": "Width", "thickness": "Thickness", "volume": "Volume", "electrode_area": "Electrode area",
    "operating_temperature_min": "Operating temperature, low",
    "operating_temperature_max": "Operating temperature, high",
    "storage_temperature_min": "Storage temperature, low",
    "storage_temperature_max": "Storage temperature, high",
    "cycle_life": "Cycle life", "calendar_life": "Calendar life",
    "capacity_retention": "Capacity retention", "energy_retention": "Energy retention",
    "state_of_health": "State of health", "self_discharge_rate": "Self-discharge",
    "round_trip_efficiency": "Round-trip efficiency", "energy_efficiency": "Energy efficiency",
    "coulombic_efficiency": "Coulombic efficiency", "first_cycle_efficiency": "First-cycle efficiency",
    "warranty_cycles": "Warranty cycles", "warranty_throughput": "Warranty throughput",
    "service_life_hours": "Service life", "leakage_current": "Leakage current",
    "knee_point_cycle": "Knee-point cycle", "resistance_growth": "Resistance growth",
    "parallel_count": "Cells in parallel", "series_count": "Cells in series",
    "cooling_capacity": "Cooling capacity", "standby_consumption": "Standby consumption",
}
GROUP_ORDER = ["Electrical", "Density", "Current and power", "Impedance", "Physical",
               "Thermal and safety", "Lifetime", "Mechanical", "System and BMS", "Sustainability"]

# The product family. Site content: one line of truth each, edited here.
FAMILY = [
    dict(key="design", name="Design", repo="battery-design", glyph="design", status="private",
         line="Cell and pack design: sizing, chemistry and layout worked through from a requirement "
              "to a bill of materials.",
         note="A cloud edition, battery-design-cloud, runs the same tools as a service."),
    dict(key="core", name="Core", repo="battery-core", glyph="core", status="open",
         href="https://morshedvarzandeh.github.io/battery-core/",
         line="Battery engineering in the open: interactive visualisations, tested models and "
              "notebooks you can run, with every assumption stated.",
         note="Chapter 1 covers cell anatomy, capacity and C-rate, production routes and ageing."),
    dict(key="data", name="Data", repo="battery-data", glyph="data", status="open", here=True,
         href="cells.html",
         line="Every published specification with the conditions it was measured under, and the "
              "sentence it was read from.",
         note=""),
    dict(key="war-room", name="War Room", repo="Battery-war-room", glyph="market", status="private",
         line="Prices, market moves and supply chain — the commercial picture behind the cells.", note=""),
    dict(key="health", name="State of Health", repo="", glyph="health", status="building",
         line="Algorithms that read state of health from field data: what a cell has left, rather "
              "than what it was sold as.", note=""),
    dict(key="worldcup", name="World Cup", repo="battery-worldcup", glyph="cup", status="building",
         line="Cells put head to head on the same measured basis, so a comparison means something.", note=""),
    dict(key="recycling", name="Recycling", repo="", glyph="recycle", status="planned",
         line="Recovery routes and second-life value — the end of the life the rest of the family "
              "designs for.", note=""),
]
STATUS = {"open": ("Open source", "good"), "private": ("Private", ""),
          "building": ("In development", ""), "planned": ("Planned", "")}

e = lambda s: html.escape("" if s is None else str(s), quote=True)


def fit_title(main: str, tail: str = BRAND, limit: int = 65) -> str:
    """A title a search result can show whole.

    Past about 65 characters the end is replaced with an ellipsis, and the end
    is where the brand sits. So the brand is what gets dropped, not the name of
    the product someone searched for.
    """
    full = f"{main} — {tail}"
    return full if len(full) <= limit else main[:limit].rstrip(" —,")


def num(v) -> str:
    """The same rounding the page used to do in JavaScript, so nothing shifts."""
    if v is None or v == "":
        return ""
    n = float(v)
    a = abs(n)
    dp = 0 if a >= 1000 else 1 if a >= 100 else 2 if a >= 1 else 4
    s = f"{n:,.{dp}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def plural(n, one, many=None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def slug(s: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in s.lower())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


# --------------------------------------------------------------------------
# What each product is, worked out once
# --------------------------------------------------------------------------
DIMQ = ("length", "width", "height", "thickness", "diameter")


def first_of(p: dict) -> dict:
    """First statement of a quantity wins, as everywhere else in the project."""
    by = {}
    for o in p["obs"]:
        by.setdefault(o["q"], o)
    return by


def dims_of(p: dict):
    """The drawn outline in millimetres, or None when nothing was published.

    Where a document gives three numbers and calls the order "as published",
    which one is the height is not knowable. The drawing stands the largest
    upright, the middle across and the smallest into the page -- the usual
    orientation of a hardcase cell -- and the label keeps the numbers in the
    order the document printed them.
    """
    by = first_of(p)
    v = lambda q: by[q]["v"] if q in by else None
    published = [o for o in p["obs"] if o["q"] in DIMQ]
    label = " × ".join(("⌀" if o["q"] == "diameter" else "") + num(o["v"]) for o in published) + " mm"
    D, H, W, L, T = v("diameter"), v("height"), v("width"), v("length"), v("thickness")
    if D is not None and H is not None:
        return {"shape": "cyl", "d": D, "h": H, "label": label}
    pool = sorted([x for x in (L, W, H, T) if x is not None], reverse=True)
    if len(pool) < 3:
        return None
    # a cylinder published as three numbers is two diameters and a height
    if abs(pool[0] - pool[1]) < 0.02 * pool[0] and T is None:
        return {"shape": "cyl", "d": pool[0], "h": pool[2], "label": label}
    if abs(pool[1] - pool[2]) < 0.02 * pool[1] and T is None:
        return {"shape": "cyl", "d": pool[1], "h": pool[0], "label": label}
    return {"shape": "box", "h": pool[0], "w": pool[1], "t": pool[2], "label": label}


def summary(p: dict) -> str:
    """The line under the name. Every clause is something the document said."""
    m, bits = p["m"], []
    what = " ".join(x for x in (FORM.get(p["fmt"], ""), p["chem"]["designation"],
                                KIND.get(p["kind"], p["kind"]).lower()) if x)
    bits.append(what[:1].upper() + what[1:])
    spec = []
    if m["ah"] is not None:
        spec.append(num(m["ah"]) + " Ah")
    elif m["wh"] is not None:
        spec.append(num(m["wh"]) + " Wh")
    if m["v"] is not None:
        spec.append("at " + num(m["v"]) + " V")
    if spec:
        bits.append(" ".join(spec))
    if m["whkg"] is not None:
        bits.append(num(m["whkg"]) + " Wh/kg" + (", derived" if m["whkg_derived"] else ""))
    return ". ".join(bits) + "."


def facts(p: dict):
    """Two or three numbers for a tile: the ones a reader picks a cell by."""
    m, by, out = p["m"], first_of(p), []
    if m["ah"] is not None:
        out.append(("Capacity", num(m["ah"]) + " Ah"))
    elif "usable_energy" in by:
        out.append(("Usable", num(by["usable_energy"]["v"]) + " " + UNIT.get(by["usable_energy"]["u"], by["usable_energy"]["u"])))
    if m["v"] is not None:
        out.append(("Voltage", num(m["v"]) + " V"))
    if m["whkg"] is not None:
        out.append(("Specific energy", num(m["whkg"]) + " Wh/kg"))
    elif "cycle_life" in by:
        out.append(("Cycle life", num(by["cycle_life"]["v"])))
    return out[:3]


def conditions(c: dict):
    """A value is only as good as what it was measured under."""
    if not c:
        return []
    out = []
    if c.get("rate_value") is not None:
        out.append(num(c["rate_value"]) + " " + (c.get("rate_unit") or "C"))
    if c.get("temperature_c") is not None:
        out.append(num(c["temperature_c"]) + " °C")
    elif c.get("temperature_reference"):
        out.append(str(c["temperature_reference"]) + " temperature")
    if c.get("voltage_upper_v") is not None:
        out.append("to " + num(c["voltage_upper_v"]) + " V")
    if c.get("voltage_lower_v") is not None:
        out.append(num(c["voltage_lower_v"]) + " V cut-off")
    if c.get("direction"):
        out.append("charge and discharge" if c["direction"] == "symmetric" else "on " + c["direction"])
    if c.get("soc_window"):
        out.append(str(c["soc_window"]).replace("-", "–") + " SOC")
    if c.get("soc_pct") is not None:
        out.append(num(c["soc_pct"]) + "% SOC")
    if c.get("dod_pct") is not None:
        out.append(num(c["dod_pct"]) + "% depth of discharge")
    if c.get("pulse_duration_s") is not None:
        out.append(num(c["pulse_duration_s"]) + " s pulse")
    if c.get("duration_s") is not None:
        s = c["duration_s"]
        out.append(num(round(s / 86400)) + " days" if s >= 86400 else
                   num(round(s / 3600)) + " hours" if s >= 3600 else num(s) + " s")
    if c.get("frequency_hz") is not None:
        f = c["frequency_hz"]
        out.append(num(f / 1000) + " kHz" if f >= 1000 else num(f) + " Hz")
    if c.get("cycle_index") is not None:
        out.append("at the first cycle" if c["cycle_index"] == 0 else "at cycle " + num(c["cycle_index"]))
    if c.get("rate_reference_capacity_ah") is not None:
        out.append("C referred to " + num(c["rate_reference_capacity_ah"]) + " Ah")
    if c.get("boundary"):
        out.append("measured at the " + str(c["boundary"]).replace("_", " "))
    if c.get("dimension_order") == "as_published":
        out.append("dimensions as published")
    return out


UNSTATED = {"temperature_c": "temperature", "temperature_reference": "temperature reference",
            "rate_value": "rate", "rate_unit": "rate", "voltage_lower_v": "cut-off voltage",
            "voltage_upper_v": "charge limit", "dod_pct": "depth of discharge",
            "soc_pct": "state of charge", "pulse_duration_s": "pulse duration",
            "direction": "direction", "boundary": "measurement boundary"}


def unstated(lst):
    out = []
    for k in lst or []:
        n = UNSTATED.get(k, k.replace("_", " "))
        if n not in out:
            out.append(n)
    return out


def qname(q: str) -> str:
    return QNAME.get(q) or q.replace("_", " ").capitalize()


def lab_inputs(p: dict):
    """What the discharge model is given, and which of it the document said."""
    by, m, assumed = first_of(p), p["m"], []
    cap = m["ah"]
    if cap is None or m["v"] is None:
        return None

    def cond(k):
        for o in p["obs"]:
            if o.get("cond") and o["cond"].get(k) is not None:
                return o["cond"][k]
        return None

    chem = (p["chem"]["designation"] or "").upper()
    flat = chem in ("LFP", "LTO") or (not chem and m["v"] < 3.4)
    vmax = cond("voltage_upper_v")
    if vmax is None:
        vmax = by["charge_cutoff_voltage"]["v"] if "charge_cutoff_voltage" in by else \
               by["absolute_max_voltage"]["v"] if "absolute_max_voltage" in by else None
    if vmax is None:
        vmax = 3.65 if flat else 4.2
        assumed.append(f"charge limit {num(vmax)} V")
    vmin = cond("voltage_lower_v")
    if vmin is None:
        vmin = by["discharge_cutoff_voltage"]["v"] if "discharge_cutoff_voltage" in by else \
               by["absolute_min_voltage"]["v"] if "absolute_min_voltage" in by else None
    if vmin is None:
        vmin = 2.5 if flat else 3.0
        assumed.append(f"cut-off {num(vmin)} V")

    ri = by.get("internal_resistance_ac") or by.get("internal_resistance_dc")
    if ri:
        r = ri["v"] * 1000 if ri["u"] == "ohm" else ri["v"]
    else:
        # resistance times capacity is roughly constant across formats
        r = round(max(0.15, 80 / cap), 2)
        assumed.append(f"internal resistance {num(r)} mΩ")
    mass = m["mass_g"] or 0
    if not mass:
        assumed.append("no mass published, so no temperature rise")
    return {"cap": cap, "vmax": vmax, "vmin": vmin, "r": r, "mass": mass,
            "flat": flat, "assumed": assumed}


# --------------------------------------------------------------------------
# The page itself
# --------------------------------------------------------------------------
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect x='9' y='6' width='14' height='22' rx='2.5' fill='none' stroke='%231d1d1f' "
           "stroke-width='2.4'/%3E%3Crect x='13' y='3' width='6' height='3' rx='1' fill='%231d1d1f'/%3E"
           "%3C/svg%3E")

NAV = [("products.html", "products", "Products"), ("cells.html", "cells", "Cell library"),
       ("makers.html", "makers", "Makers"), ("method.html", "method", "Method"),
       ("bench.html", "bench", "Bench")]


def page(*, path: str, title: str, desc: str, body: str, here: str = "",
         over_hero: bool = False, jsonld=None, head: str = "", scripts: str = "") -> str:
    """One document.

    Everything a reader needs is in the HTML before a script runs. app.js only
    draws the pictures and wires the two interactive parts, so the page is
    readable, linkable and indexable without it.
    """
    up = "../" * path.count("/")
    canon = f"{SITE_URL}/{path}" if path != "index.html" else SITE_URL + "/"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>\n'
                 for b in (jsonld or []))
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{up}{href}"{cur if here == k else ""}>{label}</a>'
                  for href, k, label in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(BRAND)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="{up}site.css">
<script>document.documentElement.className="js"</script>
{ld}{head}</head>
<body{' data-overhero="1"' if over_hero else ''}>
<a class="skip" href="#main">Skip to content</a>

<header class="nav">
  <div class="inner">
    <a class="home" href="{up}index.html">battery&#8209;data</a>
    <div class="links">{nav}<a href="{REPO}" rel="noopener">GitHub</a></div>
    <div class="spacer"></div>
    <button id="searchbtn" aria-label="Search products" title="Search (press /)">Search</button>
  </div>
</header>

<div class="searchwrap" id="searchwrap" role="dialog" aria-modal="true" aria-label="Search products">
  <div class="searchbox">
    <input id="searchinput" type="search" placeholder="Search products" autocomplete="off" spellcheck="false">
    <div class="results" id="results"></div>
    <p class="legal" style="margin-top:14px">Esc to close &middot; &uarr;&darr; to move &middot; Return to open</p>
  </div>
</div>

<main id="main">{body}</main>

{footer(up)}
<script src="{up}data.js" defer></script>
{scripts}<script src="{up}app.js" defer></script>
</body>
</html>
"""


def footer(up: str) -> str:
    return f"""<footer>
  <div class="wrap wide">
    <div class="cols">
      <div>
        <h4>Products</h4>
        <ul>
          <li><a href="{up}products.html">All products</a></li>
          <li><a href="{up}cells.html">The cell library</a></li>
          <li><a href="{up}makers.html">Manufacturers</a></li>
          <li><a href="{up}bench.html">Comparison bench</a></li>
        </ul>
      </div>
      <div>
        <h4>Understand</h4>
        <ul>
          <li><a href="{up}method.html">How a value is stored</a></li>
          <li><a href="{REPO}/blob/main/docs/02-conventions.md" rel="noopener">Conventions</a></li>
          <li><a href="{REPO}/blob/main/crosswalk/CROSSWALK.md" rel="noopener">Standards crosswalk</a></li>
        </ul>
      </div>
      <div>
        <h4>Contribute</h4>
        <ul>
          <li><a href="{REPO}/blob/main/docs/06-submitting-a-datasheet.md" rel="noopener">Submit a datasheet</a></li>
          <li><a href="{REPO}/tree/main/contrib" rel="noopener">Contribution files</a></li>
          <li><a href="{REPO}/blob/main/docs/07-candidate-review.md" rel="noopener">Review queue</a></li>
        </ul>
      </div>
      <div>
        <h4>Build on it</h4>
        <ul>
          <li><a href="{REPO}/tree/main/api" rel="noopener">Read API</a></li>
          <li><a href="{REPO}/tree/main/schema" rel="noopener">Database schema</a></li>
          <li><a href="{REPO}/tree/main/tools" rel="noopener">Ingestion tools</a></li>
        </ul>
      </div>
    </div>
    <div class="fine">
      <p class="legal">Specifications are quoted from manufacturers&rsquo; own published documents and remain the
        property of their publishers. No datasheet is redistributed here: each value is stored with the sentence it
        was read from, a link to the document and the date it was retrieved.</p>
      <p class="legal">Where a document did not state the rate, the temperature or the cut&#8209;off a value was
        measured at, this site says so rather than filling the gap. Nothing on these pages is a manufacturer&rsquo;s
        endorsement, and nothing here is a substitute for the current datasheet.</p>
      <p class="legal">battery&#8209;data &middot; open source, CC&nbsp;BY&#8209;SA&nbsp;4.0 for the data &middot;
        <a href="{REPO}" rel="noopener">github.com/Morshedvarzandeh/battery&#8209;data</a></p>
    </div>
  </div>
</footer>
"""


def art_box(rec: dict, max_px: int, reflect: bool = False, cls: str = "art") -> str:
    """A slot app.js fills with the drawing.

    It carries a uid, not a copy of the record: every page already loads the
    library index, and 64 inlined copies of the same fields cost more than the
    index itself.
    """
    refl = ' data-reflect="1"' if reflect else ""
    return f'<div class="{cls}" data-art="{e(rec["uid"])}" data-max="{max_px}"{refl}></div>'


def tile(rec: dict, up: str) -> str:
    """One product in a grid. Readable with no script; drawn once there is one."""
    badges = []
    if rec["chem"]:
        badges.append(f'<span class="badge chem">{e(rec["chem"])}</span>')
    badges.append(f'<span class="badge">{e(KIND.get(rec["kind"], rec["kind"]))}</span>')
    if rec["datasheet"]:
        badges.append('<span class="badge doc">Datasheet</span>')
    facts_html = "".join(f'<span>{e(k)} <b>{e(v)}</b></span>' for k, v in rec["facts"])
    sortkeys = (f' data-uid="{e(rec["uid"])}" data-ah="{rec["ah"] or ""}" '
                f'data-whkg="{rec["whkg"] or ""}" data-mass="{rec["mass"] or ""}"')
    return f"""<a class="tile rev" href="{up}{rec['href']}"{sortkeys}>
      {art_box(rec, 132)}
      <div><div class="maker">{e(rec['manu'])}</div><div class="name">{e(rec['model'])}</div></div>
      <div class="badges">{''.join(badges)}</div>
      <div class="facts">{facts_html}</div>
      <span class="more">Specifications</span>
    </a>"""


def family_tile(f: dict, up: str, big: bool = False) -> str:
    st = STATUS.get(f["status"], ("", ""))
    to = f.get("href") or (f"{REPO}/{f['repo']}" if False else None)
    if not to and f.get("repo") and f["status"] == "open":
        to = f"https://github.com/Morshedvarzandeh/{f['repo']}"
    if to and not to.startswith("http"):
        to = up + to
    badges = [f'<span class="badge {st[1]}">{e(st[0])}</span>']
    if f.get("repo"):
        badges.append(f'<span class="badge">{e(f["repo"])}</span>')
    if f.get("here"):
        badges.append('<span class="badge chem">You are here</span>')
    link = ""
    if to:
        label = "Open the library" if f.get("here") else ("Open " + f["name"] if f.get("href") else "See the repository")
        link = f'<p style="margin-top:16px"><span class="arrow">{e(label)}</span></p>'
    inner = f"""
      <div class="gwrap"><div data-glyph="{f['glyph']}"></div></div>
      <div class="ftext">
        <h3>{e(f['name'])}</h3>
        <p class="small">{e(f['line'])}</p>
        {f'<p class="legal" style="margin-top:8px">{e(f["note"])}</p>' if big and f.get("note") else ""}
        <div class="badges" style="margin-top:14px">{''.join(badges)}</div>
        {link}
      </div>"""
    if to:
        rel = "" if to.startswith(up) or not to.startswith("http") else ' rel="noopener"'
        return f'<a class="ftile rev" href="{e(to)}"{rel}>{inner}</a>'
    return f'<div class="ftile rev is-static">{inner}</div>'


# --------------------------------------------------------------------------
# The pages
# --------------------------------------------------------------------------
def home(recs, prods, totals) -> str:
    with_unstated = sum(1 for p in prods for o in p["obs"] if o.get("unstated"))
    pct = round(with_unstated / max(totals["observations"], 1) * 100)

    # one cell published with two capacities, both true, measured differently
    pair = None
    for p in prods:
        seen = {}
        for o in p["obs"]:
            if o["q"] != "capacity":
                continue
            if o["q"] in seen and seen[o["q"]].get("cond") != o.get("cond"):
                pair = (p, seen[o["q"]], o)
                break
            seen[o["q"]] = o
        if pair:
            break

    featured = sorted([r for r in recs if r["whkg"] is not None],
                      key=lambda r: -(r["ah"] or 0))[:10]
    rows = ""
    if pair:
        p, a, b = pair
        rows = "".join(f"""<div class="spec">
            <div class="q">{e(qname(o['q']))}{f' <span class="small">({e(STAT.get(o.get("stat"), o.get("stat")))})</span>' if o.get('stat') else ''}</div>
            <div class="v">{num(o['v'])}<small>{e(UNIT.get(o['u'], o['u']))}</small></div>
            <div class="cond">{cond_chips(o)}</div></div>""" for o in (a, b))

    makers = sorted({r["manu"] for r in recs})
    maker_tiles = "".join(
        f'<a class="maker-tile" href="m/{slug(m)}.html"><div class="n">{e(m)}</div>'
        f'<div class="c">{plural(sum(1 for r in recs if r["manu"] == m), "product")}</div></a>'
        for m in makers)

    body = f"""
  <section class="hero center scene">
    <div class="wrap">
      <p class="eyebrow rise">{e(BRAND)}</p>
      <h1 class="display rise" style="animation-delay:60ms">The whole cell,<br><span class="grad">in the open.</span></h1>
      <p class="lead rise" style="margin-top:20px;animation-delay:130ms">Design, fundamentals, market, state of health
        &mdash; a family of tools around one library, where every specification keeps the conditions it was measured
        under.</p>
      <div class="cta rise" style="margin-top:28px;animation-delay:190ms">
        <a class="btn" href="products.html">Explore the products</a>
        <a class="arrow" href="cells.html">Open the cell library</a>
      </div>
    </div>
    <figure class="scaleline wrap wide">
      <div id="land"></div>
      <figcaption>Every object is a product in the library, standing at the size its maker published, on one scale.
        Tap a marker to open it.</figcaption>
    </figure>
  </section>

  <div class="stats">
    <div><div class="v grad">{totals['products']}</div><div class="k">products</div></div>
    <div><div class="v grad">{totals['makers']}</div><div class="k">manufacturers</div></div>
    <div><div class="v grad">{totals['observations']}</div><div class="k">measured values</div></div>
    <div><div class="v grad">{totals['quotes']}</div><div class="k">source sentences</div></div>
  </div>

  <section>
    <div class="wrap wide">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:20px;flex-wrap:wrap">
        <h2 class="title rev">The family.</h2>
        <a class="arrow rev" href="products.html">Every product</a>
      </div>
      <p class="lead rev" style="margin-top:14px">One set of tools around one library. Design a cell, learn the physics,
        look up what a maker actually published, watch what the market does with it, and see what is left of it in
        service.</p>
      <div class="grid g2 rev" style="margin-top:34px">{''.join(family_tile(f, '') for f in FAMILY[:4])}</div>
      <div class="arrows rev" style="margin-top:24px"><a class="arrow" href="products.html">The three still being built</a></div>
    </div>
  </section>

  {f'''<section class="band">
    <div class="wrap">
      <h2 class="title rev">The same cell. The same page.<br>Both numbers are true.</h2>
      <p class="lead rev" style="margin-top:18px">{e(pair[0]["cell"])} is published with two capacities. Neither is
        wrong. They were measured at different rates, and a column called <span class="mono">capacity_mah</span> keeps
        one of them and quietly loses the other.</p>
      <div class="card rev" style="margin-top:34px;background:var(--card-2);border:1px solid var(--hair)">
        {rows}
        <p class="small" style="margin-top:18px">Same document, same page. The difference is the rate.</p>
      </div>
      <div class="arrows rev" style="margin-top:26px">
        <a class="arrow" href="{uid_href(pair[0]["uid"])}">See every value for this cell</a>
        <a class="arrow" href="method.html">Why the conditions are kept</a>
      </div>
    </div>
  </section>''' if pair else ''}

  <section class="stage">
    <div class="wrap center">
      <p class="eyebrow rev">Honest about the gaps</p>
      <h2 class="title rev"><span class="grad">{pct}%</span> of these values arrive<br>without their conditions.</h2>
      <p class="lead rev" style="margin-top:20px">{with_unstated} of the {totals['observations']} values in this library
        were published without the rate, the temperature or the cut-off they were taken at. That is not a flaw in the
        library &mdash; it is what the documents say. Each of those values is marked, quantity by quantity, rather than
        completed with a plausible guess.</p>
      <p class="rev" style="margin-top:26px"><span class="badge flag">temperature not stated</span></p>
      <div class="cta rev" style="margin-top:26px"><a class="arrow" href="method.html">How the gaps are recorded</a></div>
    </div>
  </section>

  <section>
    <div class="wrap wide">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:20px;flex-wrap:wrap">
        <h2 class="title rev">The cell library.</h2>
        <a class="arrow rev" href="cells.html">All {totals['products']} products</a>
      </div>
      <div class="rail" style="margin-top:30px">{''.join(tile(r, '') for r in featured)}</div>
    </div>
  </section>

  <section class="band">
    <div class="wrap wide">
      <h2 class="title rev">Made by.</h2>
      <div class="grid g4 rev" style="margin-top:30px">{maker_tiles}</div>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2 class="title rev">Open, from the schema up.</h2>
      <div class="grid g3" style="margin-top:32px">
        <div class="card plain rev">
          <h3 class="sub">Contribute a datasheet</h3>
          <p class="small" style="margin-top:12px">Open an issue with a link to the document. The values are extracted,
            reviewed against the conditions rule, and merged as a versioned file.</p>
          <p style="margin-top:16px"><a class="arrow" href="{REPO}/blob/main/docs/06-submitting-a-datasheet.md" rel="noopener">How submissions work</a></p>
        </div>
        <div class="card plain rev">
          <h3 class="sub">Query it</h3>
          <p class="small" style="margin-top:12px">A Postgres schema that refuses a capacity with no rate, and a read
            API over it. One command brings the whole thing up locally.</p>
          <p style="margin-top:16px"><a class="arrow" href="{REPO}/tree/main/api" rel="noopener">The read API</a></p>
        </div>
        <div class="card plain rev">
          <h3 class="sub">Cross the standards</h3>
          <p class="small" style="margin-top:12px">A published mapping between BDF, BattINFO, BPX and the EU Battery
            Passport &mdash; four vocabularies that had no crosswalk between them.</p>
          <p style="margin-top:16px"><a class="arrow" href="{REPO}/blob/main/crosswalk/CROSSWALK.md" rel="noopener">Read the crosswalk</a></p>
        </div>
      </div>
    </div>
  </section>"""

    ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": SITE_URL + "/",
         "description": f"{TAGLINE}. An open library of battery cells, modules and packs.",
         "publisher": {"@type": "Organization", "name": BRAND, "url": SITE_URL + "/"}},
        {"@context": "https://schema.org", "@type": "Organization", "name": BRAND,
         "url": SITE_URL + "/", "sameAs": [REPO]},
    ]
    return page(path="index.html", here="", over_hero=True, jsonld=ld,
                title=f"{BRAND} — {TAGLINE}",
                desc=(f"An open library of {totals['products']} battery cells, modules and packs from "
                      f"{totals['makers']} manufacturers. Every specification carries the rate, temperature and "
                      f"cut-off it was measured at, and the sentence it was read from."),
                body=body)


def cond_chips(o: dict) -> str:
    out = "".join(f'<span class="badge">{e(c)}</span>' for c in conditions(o.get("cond")))
    out += "".join(f'<span class="badge flag" title="The document did not state this">{e(u)} not stated</span>'
                   for u in unstated(o.get("unstated")))
    return out


def uid_href(uid: str) -> str:
    return "p/" + uid.replace("/", "-") + ".html"


def products_page(totals) -> str:
    shipped = [f for f in FAMILY if f["status"] in ("open", "private")]
    coming = [f for f in FAMILY if f["status"] in ("building", "planned")]
    body = f"""
  <section class="tight">
    <div class="wrap wide">
      <p class="eyebrow rev">Products</p>
      <h1 class="title rev">One library. {plural(len(FAMILY), 'tool')} around it.</h1>
      <p class="lead rev" style="margin-top:16px">Each of these is its own repository, with its own scope and its own
        rate of progress. What they share is the rule this library is built on: a number is kept with the conditions it
        was measured under, or it is not kept at all.</p>
    </div>
  </section>
  <section class="tight">
    <div class="wrap wide"><div class="grid g2">{''.join(family_tile(f, '', True) for f in shipped)}</div></div>
  </section>
  <section class="band">
    <div class="wrap wide">
      <h2 class="sub rev">Being built</h2>
      <p class="small rev" style="margin-top:10px;max-width:62ch">Listed because they are real work in progress, not
        because they are ready. Nothing here is announced as finished until it is.</p>
      <div class="grid g3 rev" style="margin-top:28px">{''.join(family_tile(f, '') for f in coming)}</div>
    </div>
  </section>
  <section>
    <div class="wrap">
      <h2 class="title rev">Built the same way.</h2>
      <div class="grid g3" style="margin-top:30px">
        <div class="card plain rev"><h3 class="sub">Open by default</h3>
          <p class="small" style="margin-top:12px">What can be public is public: the library, the schema, the course and
            the crosswalk. The rest is named here rather than hidden.</p></div>
        <div class="card plain rev"><h3 class="sub">Sourced, or absent</h3>
          <p class="small" style="margin-top:12px">Every number that appears in any of these tools can be traced back to
            a document. Where the document is silent, so is the tool.</p>
          <p style="margin-top:16px"><a class="arrow" href="method.html">How a value is stored</a></p></div>
        <div class="card plain rev"><h3 class="sub">One vocabulary</h3>
          <p class="small" style="margin-top:12px">Design, test data, model parameters and passport fields are four
            standards. The crosswalk between them is published, not implied.</p>
          <p style="margin-top:16px"><a class="arrow" href="{REPO}/blob/main/crosswalk/CROSSWALK.md" rel="noopener">Read the crosswalk</a></p></div>
      </div>
    </div>
  </section>"""
    ld = [{"@context": "https://schema.org", "@type": "ItemList",
           "name": "battery-data products",
           "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": f["name"],
                                "description": f["line"]} for i, f in enumerate(FAMILY)]}]
    return page(path="products.html", here="products", jsonld=ld,
                title=f"Products — {BRAND}",
                desc="Design, Core, Data, War Room, State of Health, World Cup and Recycling: one set of "
                     "battery tools around a single library of sourced specifications.",
                body=body)


def cells_page(recs, totals) -> str:
    kinds = [k for k in KIND if any(r["kind"] == k for r in recs)]
    chems = sorted({r["chem"] for r in recs if r["chem"]})
    makers = sorted({r["manu"] for r in recs})
    seg = '<button data-kind="" aria-pressed="true">All</button>' + "".join(
        f'<button data-kind="{k}" aria-pressed="false">{e(KIND_PL.get(k, KIND[k]))}</button>' for k in kinds)
    body = f"""
  <section class="tight">
    <div class="wrap wide">
      <h1 class="title rev">The cell library.</h1>
      <p class="lead rev" style="margin-top:14px">{totals['products']} products from {totals['makers']} manufacturers,
        each one a file anyone can read, check and correct.</p>
    </div>
  </section>
  <div class="filters">
    <div class="inner">
      <div class="seg" id="kindseg">{seg}</div>
      <div class="pickers">
        <select class="pick" id="manupick" aria-label="Manufacturer">
          <option value="">Every manufacturer</option>
          {''.join(f'<option value="{e(m)}">{e(m)}</option>' for m in makers)}
        </select>
        <select class="pick" id="chempick" aria-label="Chemistry">
          <option value="">Every chemistry</option>
          {''.join(f'<option value="{e(c)}">{e(c)}</option>' for c in chems)}
        </select>
        <select class="pick" id="sortpick" aria-label="Sort by">
          <option value="ah">Capacity</option><option value="whkg">Specific energy</option>
          <option value="mass">Mass</option><option value="name">Name</option>
          <option value="maker">Manufacturer</option>
        </select>
      </div>
    </div>
  </div>
  <section class="tight">
    <div class="wrap wide">
      <p class="count" id="lcount">{plural(len(recs), 'product')}</p>
      <div class="grid g3" id="grid" style="margin-top:18px">{''.join(tile(r, '') for r in recs)}</div>
    </div>
  </section>"""
    ld = [{"@context": "https://schema.org", "@type": "ItemList",
           "numberOfItems": len(recs),
           "itemListElement": [{"@type": "ListItem", "position": i + 1,
                                "url": f"{SITE_URL}/{r['href']}", "name": r["name"]}
                               for i, r in enumerate(recs)]}]
    return page(path="cells.html", here="cells", jsonld=ld,
                title=fit_title(f"Cell library — {totals['products']} sourced products"),
                desc=(f"{totals['products']} battery cells, modules and packs from {totals['makers']} manufacturers, "
                      "filterable by kind, maker and chemistry. Every value with its conditions and its source."),
                body=body, scripts='<script src="filters.js" defer></script>\n')


def makers_page(recs) -> str:
    names = sorted({r["manu"] for r in recs})
    rows = []
    for m in sorted(names, key=lambda m: -sum(1 for r in recs if r["manu"] == m)):
        own = [r for r in recs if r["manu"] == m]
        chems = sorted({r["chem"] for r in own if r["chem"]})
        docs = sum(1 for r in own if r["datasheet"])
        badges = "".join(f'<span class="badge chem">{e(c)}</span>' for c in chems)
        if docs:
            badges += f'<span class="badge doc">{docs} from datasheets</span>'
        rows.append(f"""<a class="maker-tile" href="m/{slug(m)}.html">
          <div class="n">{e(m)}</div>
          <div class="c">{plural(len(own), 'product')} · {plural(sum(r['nobs'] for r in own), 'value')}</div>
          <div class="badges" style="margin-top:10px">{badges}</div></a>""")
    body = f"""
  <section class="tight">
    <div class="wrap wide">
      <h1 class="title rev">Manufacturers.</h1>
      <p class="lead rev" style="margin-top:14px">Who published the documents behind this library, and how much of each
        one has been read.</p>
      <div class="grid g3 rev" style="margin-top:34px">{''.join(rows)}</div>
    </div>
  </section>"""
    return page(path="makers.html", here="makers",
                title=f"Manufacturers — {BRAND}",
                desc="The manufacturers behind the library: " + ", ".join(names) + ".",
                body=body)


def maker_page(m: str, recs) -> str:
    own = sorted([r for r in recs if r["manu"] == m], key=lambda r: -(r["ah"] or 0))
    obs = sum(r["nobs"] for r in own)
    body = f"""
  <section class="phero">
    <div class="wrap">
      <p class="eyebrow">Manufacturer</p>
      <h1>{e(m)}</h1>
      <p class="lead center" style="margin:16px auto 0">{plural(len(own), 'product')} in the library,
        {plural(obs, 'value')} read from {e(m)}&rsquo;s own documents.</p>
    </div>
  </section>
  <section class="tight">
    <div class="wrap wide"><div class="grid g3">{''.join(tile(r, '../') for r in own)}</div></div>
  </section>"""
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Manufacturers", "item": f"{SITE_URL}/makers.html"},
        {"@type": "ListItem", "position": 2, "name": m, "item": f"{SITE_URL}/m/{slug(m)}.html"}]}]
    return page(path=f"m/{slug(m)}.html", here="makers", jsonld=ld,
                title=fit_title(f"{m} — {plural(len(own), 'product')}"),
                desc=f"{m} cells, modules and packs in the library: {plural(len(own), 'product')} and "
                     f"{plural(obs, 'sourced value')}, each with the conditions it was measured under.",
                body=body)


def product_page(p: dict, rec: dict, recs, groups: dict) -> str:
    """One product, with every value it holds in the HTML.

    This is the page a search engine sees and the page a reader lands on. The
    specifications are written here, not assembled by a script, so both get the
    same thing.
    """
    by = first_of(p)
    group_of = {q: g for g, qs in groups.items() for q in qs}

    head_metrics, seen = [], set()
    def push(k, v, u, o):
        if v is not None and len(head_metrics) < 4 and k not in seen:
            seen.add(k)
            head_metrics.append((k, v, u, o))
    push("Capacity", p["m"]["ah"], "Ah", by.get("capacity"))
    if "usable_energy" in by:
        push("Usable energy", by["usable_energy"]["v"], UNIT.get(by["usable_energy"]["u"], by["usable_energy"]["u"]), by["usable_energy"])
    push("Nominal voltage", p["m"]["v"], "V", by.get("nominal_voltage"))
    push("Specific energy", p["m"]["whkg"], "Wh/kg", by.get("specific_energy"))
    if "cycle_life" in by:
        push("Cycle life", by["cycle_life"]["v"], "cycles", by["cycle_life"])
    g = p["m"]["mass_g"]
    if g is not None:
        push("Mass", g / 1000 if g >= 1000 else g, "kg" if g >= 1000 else "g", by.get("mass"))

    metrics = "".join(f"""<div class="metric rev">
        <div class="v">{num(v)}<small>{e(u)}</small></div>
        <div class="k">{e(k)}</div>
        {f'<div class="c">{e(" · ".join(conditions(o.get("cond"))) or ("conditions not stated" if o.get("unstated") else ""))}</div>' if o else ''}
      </div>""" for k, v, u, o in head_metrics)

    buckets = {}
    for o in p["obs"]:
        buckets.setdefault(group_of.get(o["q"], "Other"), []).append(o)
    order = [g for g in GROUP_ORDER if g in buckets] + [g for g in buckets if g not in GROUP_ORDER]

    specs = ""
    for gname in order:
        rows = ""
        for o in buckets[gname]:
            chips = cond_chips(o)
            where = " · ".join(x for x in [f"page {o['pg']}" if o.get("pg") is not None else None,
                                           "datasheet" if p["source"].get("kind") == "datasheet" else "manufacturer’s website",
                                           p["source"].get("revision"), p["source"].get("date")] if x)
            rows += f"""<div class="spec">
              <div class="q">{e(qname(o['q']))}{f' <span class="small">{e(STAT.get(o.get("stat"), o.get("stat")))}</span>' if o.get('stat') else ''}</div>
              <div class="v">{num(o['v'])}<small>{e(UNIT.get(o['u'], o['u']))}</small></div>
              {f'<div class="cond">{chips}</div>' if chips else ''}
              <div class="src"><details><summary>Where this came from</summary>
                <div class="quote"><q>{e(o['quote'])}</q>
                  <span class="attr">{e(p['source'].get('title') or p['cell'])}{' — ' + e(where) if where else ''}</span>
                </div></details></div>
            </div>"""
        specs += f'<div class="specgroup rev"><h3>{e(gname)}</h3>{rows}</div>'

    chem = p["chem"]
    bits = [(k, chem[v]) for k, v in (("Designation", "designation"), ("Cathode", "cathode"),
                                      ("Anode", "anode"), ("Electrolyte", "electrolyte"),
                                      ("Separator", "separator")) if chem.get(v)]
    if bits:
        specs += ('<div class="specgroup rev"><h3>Chemistry</h3>' + "".join(
            f'<div class="spec"><div class="q">{e(k)}</div>'
            f'<div class="v" style="font-size:17px;white-space:normal">{e(v)}</div></div>'
            for k, v in bits) + "</div>")

    src = p["source"]
    prov = []
    prov.append(("Document", e(src.get("title") or "—")))
    prov.append(("Kind", "Manufacturer datasheet" if src.get("kind") == "datasheet" else "Manufacturer website"))
    if src.get("revision"):
        prov.append(("Revision", f'<span class="mono">{e(src["revision"])}</span>'))
    if src.get("date"):
        prov.append(("Document date", f'<span class="mono">{e(src["date"])}</span>'))
    if src.get("url"):
        short = src["url"].split("://", 1)[-1]
        prov.append(("Link", f'<a href="{e(src["url"])}" rel="noopener nofollow">{e(short[:46])}{"…" if len(short) > 53 else ""}</a>'))
    if src.get("sha256"):
        prov.append(("SHA-256", f'<span class="mono" style="font-size:12px">{e(src["sha256"][:24])}…</span>'))
    prov.append(("Contribution file", f'<a href="{REPO}/blob/main/{e(p["file"])}" rel="noopener">{e(os.path.basename(p["file"]))}</a>'))
    prov.append(("Values held", f'{plural(len(p["obs"]), "value")} · {plural(len(set(o["quote"] for o in p["obs"])), "quoted sentence")}'))
    prov_html = "".join(f'<div><div class="k">{e(k)}</div><div class="v">{v}</div></div>' for k, v in prov)

    related = [r for r in recs if r["manu"] == p["manu"] and r["uid"] != p["uid"]][:8]

    inp = lab_inputs(p)
    lab = ""
    if inp:
        assumed = ("This cell&rsquo;s document did not state: " + e("; ".join(inp["assumed"])) + "."
                   if inp["assumed"] else "Every input is a value this cell&rsquo;s document stated.")
        lab = f"""
  <section class="tight">
    <div class="wrap">
      <div class="lab rev" id="lab">
        <div class="labhead">
          <h2 class="sub">Take it for a run</h2>
          <span class="badge">Model, not a measurement</span>
        </div>
        <p class="small" style="max-width:70ch">Drag the two dials. The curve is this cell discharged from full, worked
          out from its own published capacity, voltages and mass &mdash; recomputed on every frame by a Rust model
          compiled to WebAssembly.</p>
        <div class="labgrid">
          <div class="plot"><div id="labplot"></div></div>
          <div>
            <div class="knob">
              <div class="krow"><span class="kname">Discharge rate</span><span class="kval" id="labCV">1.0 C</span></div>
              <input id="labC" type="range" min="5" max="300" step="5" value="100" aria-label="Discharge rate in C">
              <p class="legal" id="labCA" style="margin-top:6px"></p>
            </div>
            <div class="knob">
              <div class="krow"><span class="kname">Temperature</span><span class="kval" id="labTV">25 °C</span></div>
              <input id="labT" type="range" min="-20" max="55" step="1" value="25" aria-label="Cell temperature in degrees Celsius">
              <div class="presets" id="labPre">
                <button data-c="20" data-t="25">Gentle</button>
                <button data-c="100" data-t="25" aria-pressed="true">Rated</button>
                <button data-c="200" data-t="25">Hard</button>
                <button data-c="100" data-t="-10">Winter</button>
              </div>
            </div>
            <div class="readout">
              <div><div class="v" id="labAh">—<small>Ah</small></div><div class="k">delivered</div></div>
              <div><div class="v" id="labWh">—<small>Wh</small></div><div class="k">energy out</div></div>
              <div><div class="v" id="labT2">—</div><div class="k">runs for</div></div>
              <div><div class="v" id="labPct">—<small>%</small></div><div class="k">of its rating</div></div>
              <div><div class="v" id="labWhkg">—<small>Wh/kg</small></div><div class="k">specific energy</div></div>
              <div><div class="v" id="labDT">—<small>K</small></div><div class="k">warms by, uncooled</div></div>
            </div>
          </div>
        </div>
        <p class="legal" style="margin-top:20px;max-width:78ch">An equivalent-circuit model: open-circuit voltage
          against state of charge for a {"flat-plateau" if inp["flat"] else "sloped"} chemistry, scaled to this
          cell&rsquo;s published voltages, less the current through its internal resistance, which rises as it gets
          colder. Heating is adiabatic at 1000 J/(kg·K). {assumed} It will not match a cycler. It is here to show which
          way the numbers move, and how far.
          <a href="{REPO}/blob/main/wasm/battery-sim/src/lib.rs" rel="noopener">Read the model</a>.</p>
      </div>
    </div>
  </section>"""

    badges = [f'<span class="badge">{e(KIND.get(p["kind"], p["kind"]))}</span>']
    if p["fmt"]:
        badges.append(f'<span class="badge">{e(FORM.get(p["fmt"], p["fmt"]))}</span>')
    if chem.get("designation"):
        badges.append(f'<span class="badge chem">{e(chem["designation"])}</span>')
    badges.append(f'<span class="badge {"doc" if src.get("kind") == "datasheet" else ""}">'
                  f'{"From the datasheet" if src.get("kind") == "datasheet" else "From the maker’s website"}</span>')

    d = rec["d"]
    body = f"""
  <section class="phero">
    <div class="wrap">
      <p class="maker"><a href="../m/{slug(p['manu'])}.html" style="color:inherit">{e(p['manu'])}</a></p>
      <h1>{e(p['model'])}</h1>
      <p class="lead center" style="margin:16px auto 0">{e(summary(p))}</p>
      <div class="badges" style="justify-content:center;margin-top:18px">{''.join(badges)}</div>
    </div>
    <figure class="pstage">
      <div>
        {art_box(rec, 300 if d else 200, reflect=True, cls="pfig")}
        <figcaption class="legal center" style="margin-top:14px">{e(d['label'] if d else 'no published dimensions')}{' · drawn to scale' if d else ''}</figcaption>
      </div>
    </figure>
  </section>

  <section class="tight">
    <div class="wrap">
      <div class="metrics">{metrics}</div>
      {'<p class="legal" style="margin-top:14px">Specific energy is not printed on this document. It is capacity × nominal voltage ÷ mass, all three of them stated values — arithmetic on facts, not a new fact.</p>' if p["m"]["whkg_derived"] else ''}
    </div>
  </section>
{lab}
  <section class="tight">
    <div class="wrap">
      <h2 class="sub rev">Specifications</h2>
      <p class="small rev" style="margin-top:8px;max-width:62ch">Every row below was read from the document named at the
        foot of this page. Grey tags are the conditions it stated; amber tags are the conditions it did not.</p>
      {specs}
    </div>
  </section>

  <section class="band">
    <div class="wrap">
      <h2 class="sub rev">Where it came from</h2>
      <div class="card rev" style="margin-top:22px;background:var(--card-2);border:1px solid var(--hair)">
        <div class="prov">{prov_html}</div>
        {f'<p class="small" style="margin-top:22px;padding-top:18px;border-top:1px solid var(--hair)">{e(src["note"])}</p>' if src.get("note") else ''}
      </div>
      <div class="arrows rev" style="margin-top:24px">
        <a class="arrow" href="../bench.html">Compare it in the bench</a>
        <a class="arrow" href="{REPO}/blob/main/{e(p['file'])}" rel="noopener">Read the raw contribution</a>
      </div>
    </div>
  </section>

  {f'''<section>
    <div class="wrap wide">
      <h2 class="sub rev">More from {e(p['manu'])}</h2>
      <div class="rail" style="margin-top:24px">{''.join(tile(r, '../') for r in related)}</div>
    </div>
  </section>''' if related else ''}"""

    props = [{"@type": "PropertyValue", "name": qname(o["q"]), "value": o["v"],
              "unitText": UNIT.get(o["u"], o["u"])} for o in p["obs"][:24]]
    ld = [{"@context": "https://schema.org", "@type": "Product", "name": p["cell"],
           "sku": p["uid"], "brand": {"@type": "Brand", "name": p["manu"]},
           "category": KIND.get(p["kind"], p["kind"]),
           "description": summary(p), "url": f"{SITE_URL}/{rec['href']}",
           "additionalProperty": props},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Cell library", "item": f"{SITE_URL}/cells.html"},
              {"@type": "ListItem", "position": 2, "name": p["manu"], "item": f"{SITE_URL}/m/{slug(p['manu'])}.html"},
              {"@type": "ListItem", "position": 3, "name": p["model"], "item": f"{SITE_URL}/{rec['href']}"}]}]

    scripts = ""
    if inp:
        scripts = (f'<script>window.BD_LAB={json.dumps(inp, ensure_ascii=False, separators=(",", ":"))};</script>\n'
                   f'<script src="../sim.js" defer></script>\n')
    key = ", ".join(x for x in [p["manu"], p["model"], chem.get("designation"),
                                FORM.get(p["fmt"], ""), KIND.get(p["kind"])] if x)
    return page(path=rec["href"], here="cells", jsonld=ld, scripts=scripts,
                title=fit_title(f"{p['cell']} specifications"),
                desc=(f"{summary(p)} {plural(len(p['obs']), 'sourced value')} from "
                      f"{src.get('title') or 'the manufacturer'}, each with the rate, temperature and cut-off it was "
                      f"measured at. {key}."),
                body=body)


def method_page(prods, totals) -> str:
    with_unstated = sum(1 for p in prods for o in p["obs"] if o.get("unstated"))
    body = f"""
  <section class="hero center">
    <div class="wrap">
      <p class="eyebrow rev">Method</p>
      <h1 class="display rev">A number is not<br>a specification.</h1>
      <p class="lead rev" style="margin-top:20px">Roughly half of what a battery datasheet calls a specification is not
        a property of the product. It is a measurement result, under conditions the document may or may not disclose.
        This library stores the conditions.</p>
    </div>
  </section>

  <section class="band">
    <div class="wrap">
      <div class="grid g2" style="gap:clamp(28px,5vw,64px)">
        <div class="rev">
          <h2 class="sub">One value, four dependencies</h2>
          <p class="lead" style="margin-top:14px;font-size:17px">A capacity depends on the rate it was drawn at, the
            temperature it was drawn at, the voltage it was drawn down to, and whether the figure is the standard,
            rated or minimum one. Store it in a column called <span class="mono">capacity_mah</span> and all four are
            gone. Here they are stored beside it, and the database refuses the value if they are missing and
            unmarked.</p>
        </div>
        <div class="rev">
          <h2 class="sub">Silence is recorded, not filled</h2>
          <p class="lead" style="margin-top:14px;font-size:17px">When a document gives a number without its conditions,
            the gap is written down as a gap. {with_unstated} values in this library carry at least one
            <span class="badge flag">not stated</span> marker. That marker is the honest answer to
            &ldquo;at what rate?&rdquo; and it is what makes the rest of the numbers trustworthy.</p>
        </div>
        <div class="rev">
          <h2 class="sub">Every value keeps its sentence</h2>
          <p class="lead" style="margin-top:14px;font-size:17px">Each value carries the sentence it was read from, the
            page it sat on and a link to the document. You can check any figure on this site against its source without
            leaving the row it appears in. Datasheet PDFs themselves are never redistributed here.</p>
        </div>
        <div class="rev">
          <h2 class="sub">Derived is labelled derived</h2>
          <p class="lead" style="margin-top:14px;font-size:17px">Specific energy is often absent from a datasheet.
            Where capacity, voltage and mass are all stated, it is computed &mdash; and said to be computed. Nothing is
            ever calculated from a value the source did not state.</p>
        </div>
      </div>
    </div>
  </section>

  <section>
    <div class="wrap">
      <h2 class="title rev">What sits underneath.</h2>
      <div class="grid g3" style="margin-top:32px">
        <div class="card plain rev"><h3 class="sub">The schema</h3>
          <p class="small" style="margin-top:12px">A Postgres schema whose constraints enforce the rule: an internal
            resistance with no method and no conditions is rejected at insert time, not flagged in review.</p>
          <p style="margin-top:16px"><a class="arrow" href="{REPO}/blob/main/docs/02-conventions.md" rel="noopener">The 27 conventions</a></p></div>
        <div class="card plain rev"><h3 class="sub">The crosswalk</h3>
          <p class="small" style="margin-top:12px">Datasheet spec, measured test data, fitted model parameters and
            regulatory passport fields are four vocabularies. This is the mapping between them.</p>
          <p style="margin-top:16px"><a class="arrow" href="{REPO}/blob/main/crosswalk/CROSSWALK.md" rel="noopener">BDF · BattINFO · BPX · Passport</a></p></div>
        <div class="card plain rev"><h3 class="sub">The bench</h3>
          <p class="small" style="margin-top:12px">The same library, in the working tool: compare products side by side,
            plot them, print a sourced report, see what is still missing.</p>
          <p style="margin-top:16px"><a class="arrow" href="bench.html">Open the bench</a></p></div>
      </div>
    </div>
  </section>"""
    return page(path="method.html", here="method",
                title=fit_title("Method — how a value is stored"),
                desc="Why a capacity is kept with its rate, temperature and cut-off; how a gap in a datasheet is "
                     "recorded rather than filled; and why a derived number says it is derived.",
                body=body)


def data_js(recs, scene) -> str:
    """The lean index every page carries: enough for search and the landscape.

    No observations, no quotes. Those live on the page that shows them, which
    is why the home page no longer downloads 138 kB to draw a hero.
    """
    lean = [{k: r[k] for k in ("uid", "name", "model", "manu", "kind", "chem", "d",
                               "shape", "href", "sub", "hay", "fact")} for r in recs]
    blob = {"products": lean, "scene": [r["uid"] for r in scene]}
    return ("/* GENERATED by tools/build_site.py -- do not edit.\n"
            "   The library's index: what search needs and what the drawing needs. */\n"
            "window.BD = " + json.dumps(blob, ensure_ascii=False, separators=(",", ":")) + ";\n"
            "window.BD.byUid = Object.fromEntries(window.BD.products.map(p => [p.uid, p]));\n"
            "window.BD.scene = window.BD.scene.map(u => window.BD.byUid[u]);\n")


def sitemap(paths) -> str:
    urls = "".join(f"  <url><loc>{SITE_URL}/{p if p != 'index.html' else ''}</loc></url>\n" for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")


def robots() -> str:
    return ("# battery-data\n"
            "User-agent: *\n"
            "Allow: /\n"
            f"Sitemap: {SITE_URL}/sitemap.xml\n")


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def records(prods):
    """The lean record behind every tile, marker and search hit."""
    out = []
    for p in prods:
        d = dims_of(p)
        f = facts(p)
        out.append({
            "uid": p["uid"], "name": p["cell"], "model": p["model"], "manu": p["manu"],
            "kind": p["kind"], "fmt": p["fmt"], "shape": p["shape"],
            "chem": p["chem"]["designation"], "d": d,
            "ah": p["m"]["ah"], "v": p["m"]["v"], "whkg": p["m"]["whkg"], "mass": p["m"]["mass_g"],
            "nobs": len(p["obs"]), "datasheet": p["source"].get("kind") == "datasheet",
            "facts": f, "fact": f[0][1] if f else "",
            "href": uid_href(p["uid"]),
            "sub": " · ".join(x for x in [p["chem"]["designation"], KIND.get(p["kind"], p["kind"]),
                                          (num(p["m"]["ah"]) + " Ah") if p["m"]["ah"] is not None else None] if x),
            "hay": " ".join(x for x in [p["cell"], p["kind"], p["fmt"], p["chem"]["designation"] or ""]).lower(),
        })
    return sorted(out, key=lambda r: (-(r["ah"] or 0), r["name"]))


def scene_of(recs):
    """What stands on the plane: sized products stepping up in height."""
    sized = sorted([r for r in recs if r["d"] and 40 <= r["d"]["h"] <= 320],
                   key=lambda r: r["d"]["h"])
    out, last = [], 0
    for r in sized:
        if r["d"]["h"] > last * 1.2:
            out.append(r)
            last = r["d"]["h"]
    while len(out) > 7:
        out.pop(1)
    return out


def build() -> dict:
    """Every generated file, as {relative path: contents}."""
    qg = bd.load(os.path.join(bd.DATA, "quantity-groups.json"))
    groups = {k: v for k, v in qg["groups"].items() if k not in qg.get("axis_only", [])}
    import glob
    import yaml
    files = sorted(glob.glob(os.path.join(ROOT, "contrib", "**", "*.y*ml"), recursive=True))
    prods = [bd.product(yaml.safe_load(open(f)), f) for f in files]

    recs = records(prods)
    by_uid = {r["uid"]: r for r in recs}
    totals = {"products": len(prods), "makers": len({p["manu"] for p in prods}),
              "observations": sum(len(p["obs"]) for p in prods),
              "quotes": sum(len({o["quote"] for o in p["obs"]}) for p in prods),
              "datasheets": sum(1 for p in prods if p["source"].get("kind") == "datasheet")}

    out = {
        "index.html": home(recs, prods, totals),
        "products.html": products_page(totals),
        "cells.html": cells_page(recs, totals),
        "makers.html": makers_page(recs),
        "method.html": method_page(prods, totals),
        "data.js": data_js(recs, scene_of(recs)),
        "robots.txt": robots(),
    }
    for m in sorted({r["manu"] for r in recs}):
        out[f"m/{slug(m)}.html"] = maker_page(m, recs)
    for p in prods:
        r = by_uid[p["uid"]]
        out[r["href"]] = product_page(p, r, recs, groups)

    pages = [k for k in out if k.endswith(".html")]
    out["sitemap.xml"] = sitemap(["index.html"] + sorted(k for k in pages if k != "index.html"))
    return out


def verify(out: dict) -> list[str]:
    """Every local link on a generated page has to land somewhere.

    Renaming a page is the easy way to leave sixty-four dead links behind, and
    a dead link is the one bug a reader always finds first.
    """
    import re
    on_disk = {"bench.html", "sim.js", "site.css", "app.js", "filters.js", "data.js"}
    bad = []
    for rel, body in out.items():
        if not rel.endswith(".html"):
            continue
        here = os.path.dirname(rel)
        for href in re.findall(r'(?:href|src)="([^"]+)"', body):
            if href.startswith(("http", "#", "mailto:", "data:")):
                continue
            target = os.path.normpath(os.path.join(here, href))
            if target not in out and target not in on_disk and \
               not os.path.exists(os.path.join(WEB, target)):
                bad.append(f"{rel} -> {href}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit non-zero if any page is out of date")
    a = ap.parse_args()

    out = build()
    broken = verify(out)
    if broken:
        for b in broken[:20]:
            print("  dead link: " + b, file=sys.stderr)
        sys.exit(f"{len(broken)} dead link(s); nothing written")

    stale, written = [], 0
    for rel, body in out.items():
        path = os.path.join(WEB, rel)
        current = open(path).read() if os.path.exists(path) else None
        if current == body:
            continue
        if a.check:
            stale.append(rel)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").write(body)
        written += 1

    if a.check:
        if stale:
            print(f"{len(stale)} generated page(s) stale, first: {', '.join(stale[:5])}. "
                  "Run: python tools/build_site.py", file=sys.stderr)
            return 1
        print(f"the site is up to date ({len(out)} generated files)")
        return 0

    kb = sum(len(v) for v in out.values()) // 1024
    print(f"wrote {written} of {len(out)} files under web/, {kb} kB in total")
    print(f"  {sum(1 for k in out if k.startswith('p/'))} product pages, "
          f"{sum(1 for k in out if k.startswith('m/'))} manufacturer pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
