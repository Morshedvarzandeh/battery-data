#!/usr/bin/env python3
"""Build the deterministic manufacturer review queue and expansion batches.

The output files are JSON documents with a ``.yaml`` suffix. JSON is a strict
subset of YAML, so the existing validator reads them without another emitter
dependency. Keeping the batch declarative and deterministic makes it possible
to reproduce every candidate and audit the source quote used for every value.

Nothing written here is accepted data. Files live under ``review/candidates``
until the repository owner approves the matching GitHub issue.
"""
from __future__ import annotations

import json
from pathlib import Path

import expansion_aug_2026

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review" / "candidates"


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


PREVIOUS_BY_UID = {
    item["uid"]: item
    for item in load_json(ROOT / "review" / "index.json", {}).get("candidates", [])
}
ISSUE_BY_UID = load_json(ROOT / "review" / "issue-map.json", {})


def observation(quantity, value, unit, quote, *, statistic=None, conditions=None,
                page=None, section=None, **extra):
    item = {
        "quantity": quantity,
        "value": value,
        "unit": unit,
        "locator": {"quote": quote},
    }
    if statistic:
        item["statistic"] = statistic
    if conditions:
        item["conditions"] = conditions
    if page:
        item["locator"]["page"] = page
    if section:
        item["locator"]["section"] = section
    item.update(extra)
    return item


def candidate(maker_slug, model_slug, *, kind, manufacturer, model, source,
              observations, chemistry=None, form_factor=None, aliases=None):
    product = {
        "uid": f"{kind}/{maker_slug}/{model_slug}",
        "kind": kind,
        "manufacturer": manufacturer,
        "model_number": model,
        "is_rechargeable": True,
    }
    if form_factor:
        product["form_factor"] = form_factor
    if aliases:
        product["aliases"] = aliases
    document = {
        "schema_version": "1",
        "product": product,
        "source": source,
        "observations": observations,
    }
    if chemistry:
        document["chemistry"] = chemistry
    return register(document)


def register(document):
    """Write one candidate file and return its index record.

    Writing is skipped for a candidate already accepted: promotion moved that
    file into ``contrib/``, and putting it back under review would offer the
    same product for approval twice.
    """
    product, source = document["product"], document["source"]
    _, maker_slug, model_slug = product["uid"].split("/", 2)
    path = OUT / maker_slug / f"{model_slug}.yaml"
    record = {
        "uid": product["uid"],
        "manufacturer": product["manufacturer"],
        "model_number": product["model_number"],
        "kind": product["kind"],
        "candidate_file": str(path.relative_to(ROOT)),
        "source_url": source.get("url"),
        "source_title": source.get("title"),
        "observation_count": len(document["observations"]),
        "state": "pending_review",
    }
    previous = PREVIOUS_BY_UID.get(product["uid"], {})
    if previous.get("state") == "accepted":
        record.update({
            "state": "accepted",
            "accepted_file": previous["accepted_file"],
            "issue_number": previous.get("issue_number"),
            "issue_url": previous.get("issue_url"),
        })
        return record

    issue = ISSUE_BY_UID.get(product["uid"], {})
    if issue:
        record.update({
            "issue_number": issue.get("issue_number"),
            "issue_url": issue.get("issue_url"),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return record


def byd(records):
    source = {
        "uid": "src/byd-battery-box-premium-hvs-hvm-v1.1",
        "kind": "datasheet",
        "title": "BYD Battery-Box Premium HVS / HVM technical parameters",
        "url": "https://bydbatterybox.com/uploads/downloads/BYD%20Battery-Box%20Premium_Datasheet_HV-AU%20V1.2%20EN-5eec6422498ad.pdf",
        "revision": "V1.1",
        "is_final": True,
        "license": "proprietary",
        "redistributable": False,
        "note": "Facts only; document body is not redistributed.",
    }
    chemistry = {
        "designation": "LFP",
        "cathode_text": "Lithium iron phosphate (cobalt-free)",
        "locator": {"page": 2, "quote": "Battery Cell Technology Lithium Iron Phosphate (cobalt-free)"},
    }
    hvs = [
        ("5.1", 2, 5.12, 25, 50, 204, 160, 230, 712, 91),
        ("7.7", 3, 7.68, 25, 50, 307, 240, 345, 945, 129),
        ("10.2", 4, 10.24, 25, 50, 409, 320, 460, 1178, 167),
        ("12.8", 5, 12.80, 25, 50, 512, 400, 576, 1411, 205),
    ]
    hvm = [
        ("8.3", 3, 8.28, 50, 75, 153, 120, 173, 945, 129, 7.65),
        ("11.0", 4, 11.04, 50, 75, 204, 160, 230, 1178, 167, 10.2),
        ("13.8", 5, 13.80, 50, 75, 256, 200, 288, 1411, 205, 12.8),
        ("16.6", 6, 16.56, 50, 75, 307, 240, 345, 1644, 243, 15.35),
        ("19.3", 7, 19.32, 50, 75, 358, 280, 403, 1877, 281, 17.9),
        ("22.1", 8, 22.08, 50, 75, 409, 320, 460, 2110, 319, 20.45),
    ]

    def add(family, row):
        model, modules, usable, current, peak, voltage, vmin, vmax, height, mass, *power = row
        table_quote = (
            f"{family} {model}: {modules} modules; Usable Energy {usable:.2f} kWh; "
            f"Max Output Current {current} A; Peak Output Current {peak} A, 5 s; "
            f"Nominal Voltage {voltage} V; Operating Voltage {vmin}~{vmax} V; "
            f"Weight {mass} kg"
        )
        obs = [
            observation("usable_energy", usable, "kWh", table_quote,
                        statistic="rated", page=2,
                        conditions={"boundary": "pack_dc", "dod_pct": 100}),
            observation("max_continuous_discharge_current", current, "A", table_quote,
                        statistic="maximum", page=2,
                        conditions={"unstated": ["temperature_c"]}),
            observation("max_pulse_discharge_current", peak, "A", table_quote,
                        statistic="maximum", page=2,
                        conditions={"pulse_duration_s": 5, "unstated": ["temperature_c"]}),
            observation("nominal_voltage", voltage, "V", table_quote,
                        statistic="nominal", page=2),
            observation("absolute_min_voltage", vmin, "V", table_quote,
                        statistic="absolute_min", page=2),
            observation("absolute_max_voltage", vmax, "V", table_quote,
                        statistic="absolute_max", page=2),
            observation("height", height, "mm", table_quote, page=2),
            observation("width", 585, "mm", table_quote, page=2),
            observation("thickness", 298, "mm", table_quote, page=2),
            observation("mass", mass, "kg", table_quote, statistic="maximum", page=2),
            observation("round_trip_efficiency", 96, "%", "Round-trip Efficiency ≥96%",
                        statistic="minimum", page=2, is_lower_bound=True,
                        conditions={"unstated": ["boundary", "rate_value", "rate_unit", "temperature_c"]}),
            observation("operating_temperature_min", -10, "°C", "Operating Temperature -10 °C to +50°C",
                        statistic="minimum", page=2,
                        conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
            observation("operating_temperature_max", 50, "°C", "Operating Temperature -10 °C to +50°C",
                        statistic="maximum", page=2,
                        conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
        ]
        if power:
            obs.append(observation("rated_power", power[0], "kW",
                                   f"Rated Power {power[0]} kW", statistic="rated", page=2,
                                   conditions={"boundary": "pack_dc", "unstated": ["temperature_c"]}))
        records.append(candidate(
            "byd", f"battery-box-premium-{family.lower()}-{model}", kind="system",
            manufacturer="BYD", model=f"Battery-Box Premium {family} {model}",
            form_factor="other", source=source, chemistry=chemistry, observations=obs,
        ))

    for row in hvs:
        add("HVS", row)
    for row in hvm:
        add("HVM", row)


def hithium(records):
    source = {
        "uid": "src/hithium-cell-lineup-2026-08-06",
        "kind": "manufacturer_web",
        "title": "HiTHIUM Battery Cells for Advanced Energy Storage Solutions",
        "url": "https://www.hithium.com/products/cell.html",
        "document_date": "2026-08-06",
        "is_final": True,
        "license": "proprietary",
        "redistributable": False,
    }
    models = [
        ("infinity-cell-1300ah", "∞Cell 1300Ah", 1300, "LFP", 10000, 190, 406, (580.2, 75.2, 234.3)),
        ("infinity-cell-n162ah", "∞Cell N162Ah", 162, "NFPP/HC", 20000, 95.2, 173, None),
        ("infinity-cell-1175ah", "∞Cell 1175Ah", 1175, "LFP", 11000, 180, 400, (580.22, 75.22, 216.31)),
        ("infinity-cell-587ah", "∞Cell 587Ah", 587, "LFP", 11000, 185, 413, (286, 73.5, 216.3)),
        ("ess-cell-314ah", "ESS Cell 314Ah", 314, "LFP", 13000, 173.2, 382.6, None),
        ("ess-cell-280ah-1p", "ESS Cell 280Ah-1P", 280, "LFP", 7000, 159.2, 341.4, None),
    ]
    for slug, model, capacity, designation, cycles, spec_e, volumetric, dims in models:
        quote = (f"{model}: {capacity} Ah; {designation}; ≥ {cycles:,} cycles; "
                 f"{'≈' if capacity == 587 else '≥'} {spec_e} Wh/kg; "
                 f"{'≈' if capacity == 587 else '≥'} {volumetric} Wh/L")
        obs = [
            observation("capacity", capacity, "Ah", quote, statistic="nominal",
                        conditions={"unstated": ["rate_value", "rate_unit", "temperature_c", "voltage_lower_v"]}),
            observation("cycle_life", cycles, "cycles", quote, statistic="minimum", is_lower_bound=True,
                        conditions={"unstated": ["temperature_c", "dod_pct", "rate_value", "rate_unit"]}),
            observation("specific_energy", spec_e, "Wh/kg", quote, statistic="minimum", is_lower_bound=capacity != 587,
                        conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
            observation("energy_density", volumetric, "Wh/L", quote, statistic="minimum", is_lower_bound=capacity != 587,
                        conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
        ]
        if dims:
            length, width, height = dims
            dim_quote = f"Dimensions (L × W × H): {length} × {width} × {height} mm"
            obs.extend([
                observation("length", length, "mm", dim_quote),
                observation("width", width, "mm", dim_quote),
                observation("height", height, "mm", dim_quote),
            ])
        if slug == "infinity-cell-n162ah":
            obs.extend([
                observation("energy_efficiency", 94, "%", "High energy efficiency ≥ 94% @1P",
                            statistic="minimum", is_lower_bound=True,
                            conditions={"rate_value": 1, "rate_unit": "P", "unstated": ["temperature_c"]}),
                observation("operating_temperature_min", -40, "°C", "Ultra-wide operating temperature range (–40°C to 60°C)",
                            statistic="minimum", conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
                observation("operating_temperature_max", 60, "°C", "Ultra-wide operating temperature range (–40°C to 60°C)",
                            statistic="maximum", conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
            ])
        if slug == "ess-cell-280ah-1p":
            obs.extend([
                observation("operating_temperature_min", -30, "°C", "Discharge: –30°C to 60°C",
                            statistic="minimum", conditions={"temperature_reference": "ambient", "direction": "discharge"}),
                observation("operating_temperature_max", 60, "°C", "Discharge: –30°C to 60°C",
                            statistic="maximum", conditions={"temperature_reference": "ambient", "direction": "discharge"}),
                observation("operating_temperature_min", 0, "°C", "Charge: 0°C to 60°C",
                            statistic="minimum", conditions={"temperature_reference": "ambient", "direction": "charge"}),
                observation("operating_temperature_max", 60, "°C", "Charge: 0°C to 60°C",
                            statistic="maximum", conditions={"temperature_reference": "ambient", "direction": "charge"}),
            ])
        chemistry = {
            "designation": designation,
            "cathode_text": "Lithium iron phosphate" if designation == "LFP" else "Sodium NFPP",
            "anode_text": "Hard carbon" if designation == "NFPP/HC" else "Not stated",
            "locator": {"quote": f"{model}: {designation}"},
        }
        records.append(candidate(
            "hithium", slug, kind="cell", manufacturer="HiTHIUM", model=model,
            form_factor="prismatic_hardcase", source=source, chemistry=chemistry,
            observations=obs,
        ))


def cnte(records):
    source = {
        "uid": "src/cnte-ci-ess-2026-08-06",
        "kind": "manufacturer_web",
        "title": "CNTE C&I Energy Storage System specifications",
        "url": "https://en.cntepower.com/ci-ess/",
        "document_date": "2026-08-06",
        "is_final": True,
        "license": "proprietary",
        "redistributable": False,
        "note": "The manufacturer states that product parameters may change; each candidate is revision-dated to retrieval.",
    }
    chemistry = {"designation": "LFP", "cathode_text": "CATL lithium iron phosphate",
                 "locator": {"quote": "CNTE’s commercial and Industrial Battery Solutions use CATL LFP battery cells"}}
    models = [
        ("star-x", "STAR X", 5644, 2800, 1331, 1165, 1497, -30, 55, (6058, 2438, 2896), None),
        ("star-h-232", "STAR H-232", 232, 100, None, 728, 936, -25, 55, (1500, 1300, 2000), 3500),
        ("star-h-254-sp", "STAR H-254 SP", 254, 125, None, 728, 936, -25, 55, (1500, 1300, 2000), 3500),
        ("star-h-plus-306ah", "STAR H-PLUS 306Ah", 254.59, 125, 832, 728, 936, -25, 55, (1000, 1450, 2100), 2300),
        ("star-h-plus-314ah", "STAR H-PLUS 314Ah", 261.24, 125, 832, 728, 936, -25, 55, (1000, 1450, 2100), 2300),
        ("star-h-max", "STAR-H MAX", 440.96, 220, 832, 728, 936, -25, 55, (1400, 1450, 2150), None),
        ("star-q", "STAR Q", 109, 50, None, None, None, -25, 55, (1270, 1340, 2094), 1800),
    ]
    for slug, model, energy, power, nominal_v, vmin, vmax, tmin, tmax, dims, mass in models:
        quote = f"Product Model {model}; Energy Capacity {energy} kWh; Rated output power {power} kW"
        obs = [
            observation("energy", energy, "kWh", quote, statistic="nominal",
                        conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
            observation("rated_power", power, "kW", quote, statistic="rated",
                        conditions={"boundary": "ac_terminal", "unstated": ["temperature_c"]}),
            observation("operating_temperature_min", tmin, "°C", f"Operating Temperature Range {tmin} to {tmax} °C",
                        statistic="minimum", conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
            observation("operating_temperature_max", tmax, "°C", f"Operating Temperature Range {tmin} to {tmax} °C",
                        statistic="maximum", conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
        ]
        if nominal_v is not None:
            obs.append(observation("nominal_voltage", nominal_v, "V", f"Rated Voltage {nominal_v} Vdc", statistic="nominal"))
        if vmin is not None:
            vquote = f"Voltage Range {vmin} to {vmax} Vdc"
            obs.extend([
                observation("absolute_min_voltage", vmin, "V", vquote, statistic="absolute_min"),
                observation("absolute_max_voltage", vmax, "V", vquote, statistic="absolute_max"),
            ])
        width, depth, height = dims
        dim_quote = f"Dimensions (W × D × H) {width} × {depth} × {height} mm"
        obs.extend([
            observation("width", width, "mm", dim_quote),
            observation("length", depth, "mm", dim_quote),
            observation("height", height, "mm", dim_quote),
        ])
        if mass:
            obs.append(observation("mass", mass, "kg", f"Weight ≈{mass / 1000:g}T", statistic="typical"))
        if slug == "star-q":
            obs.append(observation("cycle_life", 10000, "cycles", "Cycle Life (@25℃, 0.5P) ≥10000",
                                   statistic="minimum", is_lower_bound=True,
                                   conditions={"temperature_c": 25, "rate_value": 0.5, "rate_unit": "P",
                                               "unstated": ["dod_pct"]}))
        records.append(candidate(
            "cnte", slug, kind="system", manufacturer="CNTE", model=model,
            form_factor="container" if slug == "star-x" else "other",
            source=source, chemistry=chemistry, observations=obs,
        ))


def samsung(records):
    source = {
        "uid": "src/samsung-sdi-smart-battery-systems-2016",
        "kind": "datasheet",
        "title": "Samsung SDI Smart Battery Systems for Energy Storage",
        "url": "https://www.samsungsdi.com/upload/ess_brochure/Samsung%20SDI%20brochure_EN.pdf",
        "revision": "2016 product lineup",
        "is_final": True,
        "license": "proprietary",
        "redistributable": False,
    }
    models = [
        ("m2994", "M2994", 2.8, 29.6, 25.6, 33.2, (457, 185, 154), 22),
        ("m2963-m2968", "M2963 / M2968", 2.0, 29.2, 24.0, 32.8, (214, 414, 163), 17),
        ("m8994-e2", "M8994 E2", 8.39, 89.3, 76.8, 99.6, (370, 588, 160), 60),
        ("m8194-m2", "M8194 M2", 7.65, 81.4, 70.4, 91.3, (370, 588, 160), 55),
        ("m8068-p2", "M8068 P2", 5.46, 80.3, 68.2, 90.2, (370, 650, 160), 50),
    ]
    for slug, model, energy, voltage, vmin, vmax, dims, mass in models:
        quote = (f"Item {model}; Energy {energy} kWh; Nominal voltage {voltage} V; "
                 f"Operating voltage {vmin}~{vmax} V; Weight {'<' if slug.startswith('m8') else ''}{mass} kg")
        width, depth, height = dims
        obs = [
            observation("energy", energy, "kWh", quote, statistic="nominal", page=4,
                        conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
            observation("nominal_voltage", voltage, "V", quote, statistic="nominal", page=4),
            observation("absolute_min_voltage", vmin, "V", quote, statistic="absolute_min", page=4),
            observation("absolute_max_voltage", vmax, "V", quote, statistic="absolute_max", page=4),
            observation("width", width, "mm", f"Dimension (W x D x H) {width} x {depth} x {height} mm", page=4),
            observation("length", depth, "mm", f"Dimension (W x D x H) {width} x {depth} x {height} mm", page=4),
            observation("height", height, "mm", f"Dimension (W x D x H) {width} x {depth} x {height} mm", page=4),
            observation("mass", mass, "kg", quote, statistic="maximum" if slug.startswith("m8") else "nominal",
                        page=4, is_upper_bound=slug.startswith("m8")),
        ]
        records.append(candidate(
            "samsung-sdi", slug, kind="module", manufacturer="Samsung SDI", model=model,
            form_factor="other", source=source, observations=obs,
        ))


def lg(records):
    source = {
        "uid": "src/lg-energy-solution-home-battery-eu-2026-08-06",
        "kind": "manufacturer_web",
        "title": "LG Energy Solution Home Battery product information",
        "url": "https://www.lgessbattery.com/m/eu/home-battery/product-info.lg",
        "document_date": "2026-08-06",
        "is_final": True,
        "license": "proprietary",
        "redistributable": False,
    }
    models = [
        ("resu7h-type-r", "RESU7H (Type-R)", 7.0, 6.6, 75.0, (744, 692, 206)),
        ("resu10h-type-r", "RESU10H (Type-R)", 9.8, 9.3, 97.0, (744, 907, 206)),
        ("resu10h-type-c", "RESU10H (Type-C)", 9.8, 9.3, 99.8, (744, 907, 206)),
        ("10h-prime", "10H Prime", None, 9.6, 111.0, (504, 817, 295)),
        ("16h-prime", "16H Prime", None, 16.0, 159.0, (504, 1086, 295)),
    ]
    for slug, model, total, usable, mass, dims in models:
        width, height, depth = dims
        quote = (f"{model}: " + (f"Total Energy {total} kWh; " if total is not None else "") +
                 f"Usable Energy {usable} kWh; Weight {mass} kg; "
                 f"Dimensions {width} x {height} x {depth} mm; IP55")
        obs = [
            observation("usable_energy", usable, "kWh", quote, statistic="rated",
                        conditions={"boundary": "pack_dc", "unstated": ["dod_pct"]}),
            observation("mass", mass, "kg", quote, statistic="nominal"),
            observation("width", width, "mm", quote),
            observation("height", height, "mm", quote),
            observation("thickness", depth, "mm", quote),
        ]
        if total is not None:
            obs.insert(0, observation("energy", total, "kWh", quote, statistic="nominal",
                                      conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}))
        records.append(candidate(
            "lg-energy-solution", slug, kind="pack", manufacturer="LG Energy Solution", model=model,
            form_factor="other", source=source, observations=obs,
        ))


def catl(records):
    chemistry = {"designation": "LFP", "cathode_text": "Lithium iron phosphate",
                 "locator": {"quote": "CATL describes the product as LFP-based"}}
    products = [
        {
            "slug": "enerone", "model": "EnerOne", "date": "2022-05-11",
            "url": "https://www.catl.com/en/news/935.html",
            "title": "CATL’s EnerOne battery storage system won ees AWARD 2022",
            "obs": [
                observation("energy", 372.7, "kWh", "It has a nominal capacity of 372.7 kWh", statistic="nominal",
                            conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
                observation("absolute_min_voltage", 600, "V", "suitable for inverters with operating voltages ranging from 600 to 1500 volts", statistic="absolute_min"),
                observation("absolute_max_voltage", 1500, "V", "suitable for inverters with operating voltages ranging from 600 to 1500 volts", statistic="absolute_max"),
                observation("operating_temperature_min", -30, "°C", "adaptability to ambient temperature range of -30 to +55 ℃", statistic="minimum",
                            conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
                observation("operating_temperature_max", 55, "°C", "adaptability to ambient temperature range of -30 to +55 ℃", statistic="maximum",
                            conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
            ],
        },
        {
            "slug": "tener", "model": "TENER", "date": "2024-04-09",
            "url": "https://www.catl.com/en/news/6232.html",
            "title": "CATL unveils TENER 6.25 MWh energy storage system",
            "obs": [
                observation("energy", 6250, "kWh", "TENER achieves an impressive 6.25 MWh capacity in the TEU container", statistic="nominal",
                            conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
                observation("energy_density", 430, "Wh/L", "achieving an energy density of 430 Wh/L", statistic="nominal",
                            conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
            ],
        },
        {
            "slug": "tener-stack", "model": "TENER Stack", "date": "2025-05-07",
            "url": "https://www.catl.com/en/news/6410.html",
            "title": "CATL launches 9 MWh TENER Stack",
            "obs": [
                observation("energy", 9000, "kWh", "The internal capacity reaches up to 9MWh", statistic="maximum", is_upper_bound=True,
                            conditions={"unstated": ["rate_value", "rate_unit", "temperature_c"]}),
            ],
        },
        {
            "slug": "tener-flex", "model": "TENER Flex", "date": "2024-09-25",
            "url": "https://www.catl.com/en/news/6291.html?pagesense_source=531883000126269001",
            "title": "CATL unveils TENER Flex rack energy storage system",
            "obs": [
                observation("operating_temperature_min", -40, "°C", "Withstanding temperatures from -40°C to 60°C", statistic="minimum",
                            conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
                observation("operating_temperature_max", 60, "°C", "Withstanding temperatures from -40°C to 60°C", statistic="maximum",
                            conditions={"temperature_reference": "ambient", "direction": "symmetric"}),
            ],
        },
    ]
    for item in products:
        source = {
            "uid": f"src/catl-{item['slug']}-{item['date']}",
            "kind": "manufacturer_web",
            "title": item["title"],
            "url": item["url"],
            "document_date": item["date"],
            "is_final": True,
            "license": "proprietary",
            "redistributable": False,
        }
        records.append(candidate(
            "catl", item["slug"], kind="system", manufacturer="CATL", model=item["model"],
            form_factor="rack" if item["slug"] in {"enerone", "tener-flex"} else "container",
            source=source, chemistry=chemistry, observations=item["obs"],
        ))


def recovered(records):
    """Emit the candidates re-derived from their own review issues.

    Their declaration is a data file rather than a builder above because the
    extraction that produced them is gone: ``tools/recover_issue_candidates.py``
    rebuilt each one from the issue the owner reviews, and that JSON is the
    checked-in record of what it found.
    """
    for batch in sorted((ROOT / "review" / "batches").glob("*.json")):
        for entry in json.loads(batch.read_text())["candidates"]:
            records.append(register(entry["document"]))


def main():
    records = []
    for builder in (byd, hithium, cnte, samsung, lg, catl, recovered):
        builder(records)
    expansion_aug_2026.build(records, register, observation)
    index = {
        "schema_version": 1,
        "batch": "2026-08-16-100-plus-cell-expansion",
        "status": "pending_review",
        "approval_rule": "Repository owner checks the approval box on the matching GitHub issue.",
        "candidate_count": sum(item["state"] == "pending_review" for item in records),
        "total_record_count": len(records),
        "candidates": records,
    }
    (ROOT / "review").mkdir(exist_ok=True)
    (ROOT / "review" / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"wrote {len(records)} review candidates")


if __name__ == "__main__":
    main()
