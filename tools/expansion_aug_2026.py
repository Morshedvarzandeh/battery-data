"""Source-backed micro-cell expansion retrieved on 2026-08-16.

The compact tables below are declarations, not accepted data.  The regular
review builder turns each row into one pending candidate and one owner-review
issue payload.  Values come only from the linked manufacturer tables.
"""
from __future__ import annotations

import re


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _chemistry(designation, cathode, anode, quote, *, electrolyte=None,
               section=None, page=None):
    locator = {"quote": quote}
    if section:
        locator["section"] = section
    if page:
        locator["page"] = page
    result = {"designation": designation, "locator": locator}
    if cathode:
        result["cathode_text"] = cathode
    if anode:
        result["anode_text"] = anode
    if electrolyte:
        result["electrolyte_text"] = electrolyte
    return result


def _candidate(register, *, maker_slug, manufacturer, model, kind,
               rechargeable, form_factor, source, observations, chemistry,
               form_factor_code=None):
    document = {
        "schema_version": "1",
        "product": {
            "uid": f"{kind}/{maker_slug}/{_slug(model)}",
            "kind": kind,
            "manufacturer": manufacturer,
            "model_number": model,
            "form_factor": form_factor,
            "is_rechargeable": rechargeable,
        },
        "source": source,
        "chemistry": chemistry,
        "observations": observations,
    }
    if form_factor_code:
        document["product"]["form_factor_code"] = form_factor_code
    return register(document)


def _physical_observations(observation, *, model, voltage, capacity_mah,
                           diameter, height, mass_g, quote, conditions,
                           mass_statistic=None, section=None,
                           field_quotes=None, field_sections=None):
    field_quotes = field_quotes or {}
    field_sections = field_sections or {}

    def locator_quote(quantity):
        return field_quotes.get(quantity, quote)

    def locator_section(quantity):
        return field_sections.get(quantity, section)

    return [
        observation(
            "capacity", capacity_mah / 1000, "Ah", locator_quote("capacity"),
            statistic="nominal", conditions=conditions,
            section=locator_section("capacity"),
        ),
        observation(
            "nominal_voltage", voltage, "V",
            locator_quote("nominal_voltage"), statistic="nominal",
            section=locator_section("nominal_voltage"),
        ),
        observation(
            "diameter", diameter, "mm", locator_quote("diameter"),
            section=locator_section("diameter"),
        ),
        observation(
            "height", height, "mm", locator_quote("height"),
            section=locator_section("height"),
        ),
        observation(
            "mass", mass_g, "g", locator_quote("mass"),
            statistic=mass_statistic, section=locator_section("mass"),
        ),
    ]


def _maxell_number(value):
    """Format a manufacturer-table value without inventing precision."""
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _maxell_physical_quotes(*, model, voltage, capacity_mah, current,
                             current_unit, diameter, height, mass_g,
                             cutoff_voltage):
    """Create labelled, normalized transcriptions of Maxell table cells.

    Maxell presents several product families with models as columns.  These
    strings deliberately combine the exact table headers with one model's
    values instead of pretending that a contiguous row exists in the HTML.
    Source notes disclose the normalized separators and numeric formatting.
    """
    value = _maxell_number
    return {
        "capacity": (
            f"Model {model}; Nominal Capacity (mAh) {value(capacity_mah)}; "
            f"Nominal Discharge Current ({current_unit}) {value(current)}; "
            f"voltage drops to {value(cutoff_voltage)} V at 20 deg. C"
        ),
        "nominal_voltage": (
            f"Model {model}; Nominal Voltage (V) {value(voltage)}"
        ),
        "diameter": f"Model {model}; Diameter (mm) {value(diameter)}",
        "height": f"Model {model}; Height (mm) {value(height)}",
        "mass": f"Model {model}; Weight (g) {value(mass_g)}",
    }


MAXELL_SR_SW = [
    ("SR44SW", 165, 200, 11.6, 5.4, 2.1),
    ("SR43SW", 125, 100, 11.6, 4.2, 1.7),
    ("SR1136SW", 100, 100, 11.6, 3.6, 1.6),
    ("SR1130SW", 83, 100, 11.6, 3.05, 1.2),
    ("SR1120SW", 55, 100, 11.6, 2.05, 1.0),
    ("SR1116SW", 29, 50, 11.6, 1.65, 0.7),
    ("SR936SW", 71, 100, 9.5, 3.6, 0.9),
    ("SR927SW", 55, 100, 9.5, 2.73, 0.8),
    ("SR920SW", 45, 50, 9.5, 2.05, 0.7),
    ("SR916SW", 26.5, 50, 9.5, 1.65, 0.5),
    ("SR914SW", 22, 35, 9.5, 1.45, 0.45),
    ("SR41SW", 45, 50, 7.9, 3.6, 0.7),
    ("SR731SW", 36, 50, 7.9, 3.1, 0.7),
    ("SR726SW", 35, 50, 7.9, 2.6, 0.5),
    ("SR721SW", 25, 30, 7.9, 2.1, 0.45),
    ("SR716SW", 23, 30, 7.9, 1.68, 0.3),
    ("SR712SW", 10, 20, 7.9, 1.29, 0.25),
    ("SR626SW", 30, 30, 6.8, 2.6, 0.4),
    ("SR621SW", 23, 30, 6.8, 2.15, 0.3),
    ("SR616SW", 16, 20, 6.8, 1.65, 0.3),
    ("SR527SW", 17, 30, 5.8, 2.7, 0.3),
    ("SR521SW", 16, 20, 5.8, 2.15, 0.2),
    ("SR516SW", 12.5, 20, 5.8, 1.65, 0.2),
    ("SR512SW", 5.5, 5, 5.8, 1.25, 0.14),
    ("SR421SW", 12, 20, 4.8, 2.15, 0.17),
    ("SR416SW", 8.3, 10, 4.8, 1.65, 0.12),
]

MAXELL_SR_W = [
    ("SR44W", 165, 200, 11.6, 5.4, 2.1),
    ("SR43W", 125, 200, 11.6, 4.2, 1.8),
    ("SR1130W", 79, 100, 11.6, 3.05, 1.2),
    ("SR1120W", 55, 100, 11.6, 2.05, 1.0),
    ("SR936W", 75, 100, 9.5, 3.6, 0.9),
    ("SR927W", 60, 100, 9.5, 2.73, 0.8),
    ("SR920W", 39, 100, 9.5, 2.05, 0.6),
    ("SR916W", 23, 50, 9.5, 1.65, 0.5),
    ("SR41W", 39, 50, 7.9, 3.6, 0.7),
    ("SR726W", 28, 50, 7.9, 2.6, 0.5),
    ("SR721W", 25, 50, 7.9, 2.1, 0.45),
    ("SR716W", 18, 30, 7.9, 1.68, 0.3),
    ("SR626W", 30, 50, 6.8, 2.6, 0.4),
    ("SR621W", 18, 50, 6.8, 2.15, 0.3),
]

MAXELL_LR = [
    ("LR44", 120, 100, 11.6, 5.4, 1.9),
    ("LR43", 75, 100, 11.6, 4.2, 1.5),
    ("LR1130", 45, 100, 11.6, 3.05, 1.2),
    ("LR1120", 55, 100, 11.6, 2.05, 0.9),
    ("LR41", 25, 70, 7.9, 3.6, 0.6),
]

MAXELL_CR = [
    ("CR2032", 220, 0.2, 20.0, 3.2, 3.0),
    ("CR2032H", 240, 0.2, 20.0, 3.2, 3.0),
    ("CR2032S", 250, 0.2, 20.0, 3.2, 2.8),
    ("CR1216", 25, 0.1, 12.5, 1.6, 0.6),
    ("CR1220", 36, 0.1, 12.5, 2.0, 0.8),
    ("CR1616", 55, 0.1, 16.0, 1.6, 1.1),
    ("CR1620", 80, 0.1, 16.0, 2.0, 1.3),
    ("CR1632", 140, 0.1, 16.0, 3.2, 1.9),
    ("CR2016", 90, 0.1, 20.0, 1.6, 1.7),
    ("CR2025", 170, 0.2, 20.0, 2.5, 2.5),
]

MAXELL_CR_HR = [
    ("CR2032HRS", 200, 0.2, 20.0, 3.2, 3.0),
    ("CR2032HR", 200, 0.2, 20.0, 3.2, 3.0),
    ("CR2050HR", 350, 0.2, 20.0, 5.0, 4.1),
    ("CR2450HR", 550, 0.2, 24.5, 5.0, 6.8),
]

MAXELL_CR_CYL = [
    ("CR17335A", 1650, 5, 17.0, 33.5, 17),
    ("CR17450A", 2500, 5, 17.0, 45.0, 22),
    ("CR17450AH", 3000, 1, 17.0, 45.0, 24),
    ("CR17500AU", 3500, 1, 17.0, 50.0, 26),
]

MAXELL_ML = [
    ("ML2016H", 30, 200, 20.0, 1.6, 1.7, 1500, 40),
    ("ML2032", 65, 200, 20.0, 3.2, 3.0, 1000, 30),
]


def _maxell(records, register, observation):
    normalized_table_note = (
        "Locator quotes are model-specific normalized transcriptions of the "
        "manufacturer's Specifications table. Header labels and values are "
        "preserved; separators, whitespace, trailing zeros, and footnote markers "
        "may be normalized. "
        "The live HTML page states no document revision or pagination and says "
        "that data and dimensions are not guaranteed."
    )
    sr_source = {
        "uid": "src/maxell-sr-lr-web-2026-08-16",
        "kind": "manufacturer_web",
        "title": "Silver Oxide Batteries (SR)/Alkaline Button Batteries (LR)",
        "url": "https://biz.maxell.com/en/primary_batteries/sr_coin.html",
        "license": "proprietary",
        "redistributable": False,
        "note": (
            "Retrieved 2026-08-16. Manufacturer table; the nominal-capacity "
            "footnote supplies load, 20 °C and 1.2 V cutoff conditions. "
            + normalized_table_note
        ),
    }
    sr_chem = _chemistry(
        "silver oxide / zinc", "silver oxide", "zinc",
        "uses silver oxide and zinc as the main positive electrode and negative electrode active materials",
    )
    lr_chem = _chemistry(
        "alkaline manganese / zinc", "manganese dioxide", "zinc",
        "2MnO2+Zn+H2O → 2MnOOH+ZnO",
    )
    for row in MAXELL_SR_SW + MAXELL_SR_W:
        model, cap, current_ua, diameter, height, mass = row
        section = (
            "Specifications > SR: Long-life low-drain type (SW)"
            if model.endswith("SW") else
            "Specifications > SR: High-drain type (W)"
        )
        obs = _physical_observations(
            observation, model=model, voltage=1.55, capacity_mah=cap,
            diameter=diameter, height=height, mass_g=mass,
            quote=f"Model {model}",
            conditions={"rate_value": current_ua / 1000, "rate_unit": "mA",
                        "temperature_c": 20, "voltage_lower_v": 1.2},
            section=section,
            field_quotes=_maxell_physical_quotes(
                model=model, voltage=1.55, capacity_mah=cap,
                current=current_ua, current_unit="µA", diameter=diameter,
                height=height, mass_g=mass, cutoff_voltage=1.2,
            ),
            field_sections={
                "capacity": f"{section}; nominal-capacity footnote",
            },
        )
        records.append(_candidate(
            register, maker_slug="maxell", manufacturer="Maxell", model=model,
            kind="primary_cell", rechargeable=False, form_factor="button",
            source=sr_source, observations=obs, chemistry=sr_chem,
        ))
    for model, cap, current_ua, diameter, height, mass in MAXELL_LR:
        section = "Specifications > LR: Alkaline button batteries"
        obs = _physical_observations(
            observation, model=model, voltage=1.5, capacity_mah=cap,
            diameter=diameter, height=height, mass_g=mass,
            quote=f"Model {model}",
            conditions={"rate_value": current_ua / 1000, "rate_unit": "mA",
                        "temperature_c": 20, "voltage_lower_v": 1.2},
            section=section,
            field_quotes=_maxell_physical_quotes(
                model=model, voltage=1.5, capacity_mah=cap,
                current=current_ua, current_unit="µA", diameter=diameter,
                height=height, mass_g=mass, cutoff_voltage=1.2,
            ),
            field_sections={
                "capacity": f"{section}; nominal-capacity footnote",
            },
        )
        records.append(_candidate(
            register, maker_slug="maxell", manufacturer="Maxell", model=model,
            kind="primary_cell", rechargeable=False, form_factor="button",
            source=sr_source, observations=obs, chemistry=lr_chem,
        ))

    cr_source = {
        "uid": "src/maxell-cr-coin-web-2026-08-16",
        "kind": "manufacturer_web",
        "title": "Coin Type Lithium Manganese Dioxide Batteries (CR)",
        "url": "https://biz.maxell.com/en/primary_batteries/cr_coin.html",
        "license": "proprietary",
        "redistributable": False,
        "note": (
            "Retrieved 2026-08-16. " + normalized_table_note + " "
            "When using these batteries at temperatures outside the range "
            "of 0 to +40 deg. C, Maxell instructs users to consult it in "
            "advance for conditions of use."
        ),
    }
    cr_chem = _chemistry(
        "Li/MnO2", "manganese dioxide (MnO2)", "lithium (Li)",
        "uses manganese dioxide (MnO2) as its positive active material, lithium (Li) as its negative active material, and an organic electrolyte",
        electrolyte="organic electrolyte",
        section="Principle and Reactions",
    )
    for model, cap, current_ma, diameter, height, mass in MAXELL_CR:
        obs = _physical_observations(
            observation, model=model, voltage=3, capacity_mah=cap,
            diameter=diameter, height=height, mass_g=mass,
            quote=f"Model {model}",
            conditions={"rate_value": current_ma, "rate_unit": "mA",
                        "temperature_c": 20, "voltage_lower_v": 2.0},
            section="Specifications",
            field_quotes=_maxell_physical_quotes(
                model=model, voltage=3, capacity_mah=cap,
                current=current_ma, current_unit="mA", diameter=diameter,
                height=height, mass_g=mass, cutoff_voltage=2.0,
            ),
            field_sections={
                "capacity": "Specifications; nominal-capacity footnote",
            },
        )
        for quantity, value, statistic in (("operating_temperature_min", -20, "minimum"),
                                           ("operating_temperature_max", 85, "maximum")):
            obs.append(observation(
                quantity, value, "°C",
                f"Model {model}; Operating Temperature Range (deg. C) -20 to +85",
                statistic=statistic, section="Specifications; Warnings",
                conditions={"unstated": ["temperature_reference", "direction"]},
            ))
        records.append(_candidate(
            register, maker_slug="maxell", manufacturer="Maxell", model=model,
            kind="primary_cell", rechargeable=False, form_factor="coin",
            source=cr_source, observations=obs, chemistry=cr_chem,
        ))

    hr_source = {
        "uid": "src/maxell-cr-heat-resistant-web-2026-08-16",
        "kind": "manufacturer_web",
        "title": "Heat Resistant Coin Type Lithium Manganese Dioxide Batteries (CR)",
        "url": "https://biz.maxell.com/en/primary_batteries/cr_heat-resisting.html",
        "license": "proprietary",
        "redistributable": False,
        "note": (
            "Retrieved 2026-08-16. " + normalized_table_note + " "
            "When using at temperatures exceeding 85 deg. C, Maxell "
            "instructs users to consult it in advance for conditions of use. "
            "These products are available only to equipment manufacturers as "
            "built-in parts and are not supplied directly as replacements."
        ),
    }
    hr_chem = _chemistry(
        "Li/MnO2", "manganese dioxide (MnO2)", "lithium (Li)",
        "uses manganese dioxide (MnO2) as its positive active material, lithium (Li) as its negative active material and an organic electrolyte",
        electrolyte="organic electrolyte",
        section="Principle and Reactions",
    )
    for model, cap, current_ma, diameter, height, mass in MAXELL_CR_HR:
        obs = _physical_observations(
            observation, model=model, voltage=3, capacity_mah=cap,
            diameter=diameter, height=height, mass_g=mass,
            quote=f"Model {model}",
            conditions={"rate_value": current_ma, "rate_unit": "mA",
                        "temperature_c": 20, "voltage_lower_v": 2.0},
            section="Specifications",
            field_quotes=_maxell_physical_quotes(
                model=model, voltage=3, capacity_mah=cap,
                current=current_ma, current_unit="mA", diameter=diameter,
                height=height, mass_g=mass, cutoff_voltage=2.0,
            ),
            field_sections={
                "capacity": "Specifications; nominal-capacity footnote",
            },
        )
        for quantity, value, statistic in (("operating_temperature_min", -40, "minimum"),
                                           ("operating_temperature_max", 125, "maximum")):
            obs.append(observation(
                quantity, value, "°C",
                f"Model {model}; Operating Temperature Range (deg. C) -40 to +125",
                statistic=statistic, section="Specifications; Warnings",
                conditions={"unstated": ["temperature_reference", "direction"]},
            ))
        records.append(_candidate(
            register, maker_slug="maxell", manufacturer="Maxell", model=model,
            kind="primary_cell", rechargeable=False, form_factor="coin",
            source=hr_source, observations=obs, chemistry=hr_chem,
        ))

    cyl_source = {
        "uid": "src/maxell-cr-cylindrical-web-2026-08-16",
        "kind": "manufacturer_web",
        "title": "Cylindrical Type Lithium Manganese Dioxide Batteries (CR)",
        "url": "https://biz.maxell.com/en/primary_batteries/cr_cylinder.html",
        "license": "proprietary",
        "redistributable": False,
        "note": (
            "Retrieved 2026-08-16. " + normalized_table_note + " "
            "When using at temperatures exceeding 60 deg. C, Maxell "
            "instructs users to consult it in advance for conditions of use. "
            "These products are available only to equipment manufacturers as "
            "built-in parts and are not supplied directly as replacements."
        ),
    }
    cyl_chem = _chemistry(
        "Li/MnO2", "manganese dioxide (MnO2)", "lithium (Li)",
        "uses manganese dioxide (MnO2) as its positive active material and lithium (Li) as its negative active material",
        section="Principle and Reactions",
    )
    for model, cap, current_ma, diameter, height, mass in MAXELL_CR_CYL:
        cutoff = 1.5 if model == "CR17500AU" else 2.0
        obs = _physical_observations(
            observation, model=model, voltage=3, capacity_mah=cap,
            diameter=diameter, height=height, mass_g=mass,
            quote=f"Model {model}",
            conditions={"rate_value": current_ma, "rate_unit": "mA",
                        "temperature_c": 20, "voltage_lower_v": cutoff},
            section="Specifications",
            field_quotes=_maxell_physical_quotes(
                model=model, voltage=3, capacity_mah=cap,
                current=current_ma, current_unit="mA", diameter=diameter,
                height=height, mass_g=mass, cutoff_voltage=cutoff,
            ),
            field_sections={
                "capacity": "Specifications; nominal-capacity footnote",
            },
        )
        for quantity, value, statistic in (("operating_temperature_min", -40, "minimum"),
                                           ("operating_temperature_max", 85, "maximum")):
            obs.append(observation(
                quantity, value, "°C",
                f"Model {model}; Operating Temperature Range (deg. C) -40 to +85",
                statistic=statistic, section="Specifications; Warnings",
                conditions={"unstated": ["temperature_reference", "direction"]},
            ))
        records.append(_candidate(
            register, maker_slug="maxell", manufacturer="Maxell", model=model,
            kind="primary_cell", rechargeable=False, form_factor="cylindrical",
            source=cyl_source, observations=obs, chemistry=cyl_chem,
        ))

    ml_source = {
        "uid": "src/maxell-ml-web-2026-08-16",
        "kind": "manufacturer_web",
        "title": "Coin Type Lithium Manganese Dioxide Rechargeable Batteries (ML)",
        "url": "https://biz.maxell.com/en/rechargeable_batteries/ml.html",
        "license": "proprietary",
        "redistributable": False,
        "note": (
            "Retrieved 2026-08-16. " + normalized_table_note + " "
            "These products are available only to equipment manufacturers as "
            "built-in parts and are not supplied directly as replacements."
        ),
    }
    ml_chem = _chemistry(
        "lithium manganese dioxide rechargeable (ML)",
        "specially treated manganese dioxide",
        "lithium-aluminum compound",
        "using specially treated manganese dioxide for the positive mateiral, a lithium-aluminum compound for the negative material and a specially formulated organic electrolyte",
        electrolyte="specially formulated organic electrolyte",
        section="Principle and Reactions",
    )
    for model, cap, current_ua, diameter, height, mass, cycles_10, cycles_100 in MAXELL_ML:
        obs = _physical_observations(
            observation, model=model, voltage=3, capacity_mah=cap,
            diameter=diameter, height=height, mass_g=mass,
            quote=f"Model {model}",
            conditions={"rate_value": current_ua / 1000, "rate_unit": "mA",
                        "temperature_c": 20, "voltage_lower_v": 2.0},
            section="Specifications",
            field_quotes=_maxell_physical_quotes(
                model=model, voltage=3, capacity_mah=cap,
                current=current_ua, current_unit="µA", diameter=diameter,
                height=height, mass_g=mass, cutoff_voltage=2.0,
            ),
            field_sections={
                "capacity": "Specifications; nominal-capacity footnote",
            },
        )
        for cycles, dod in ((cycles_10, 10), (cycles_100, 100)):
            obs.append(observation(
                "cycle_life", cycles, "cycles",
                f"Model {model}; Charge/Discharge Cycle Lifetime; Depth of Discharge = {dod}%; {cycles}",
                section="Specifications > Charge/Discharge Cycle Lifetime",
                conditions={"dod_pct": dod,
                            "unstated": ["temperature_c", "rate_value", "rate_unit"]},
            ))
        for quantity, value, statistic in (("operating_temperature_min", -20, "minimum"),
                                           ("operating_temperature_max", 60, "maximum")):
            obs.append(observation(
                quantity, value, "°C",
                f"Model {model}; Operating Temperature Range (deg. C) -20 to +60",
                statistic=statistic, section="Specifications",
                conditions={"unstated": ["temperature_reference", "direction"]},
            ))
        records.append(_candidate(
            register, maker_slug="maxell", manufacturer="Maxell", model=model,
            kind="cell", rechargeable=True, form_factor="coin",
            source=ml_source, observations=obs, chemistry=ml_chem,
        ))


PANASONIC_CR = [
    ("CR1025", 30, 0.1, 10.0, 2.5, 0.6, -30, 85),
    ("CR1216", 25, 0.1, 12.5, 1.6, 0.7, -30, 85),
    ("CR1220", 35, 0.1, 12.5, 2.0, 0.9, -30, 85),
    ("CR1616", 55, 0.1, 16.0, 1.6, 1.0, -30, 85),
    ("CR1620", 75, 0.1, 16.0, 2.0, 1.3, -30, 85),
    ("CR1632", 140, 0.1, 16.0, 3.2, 1.9, -30, 85),
    ("CR2012", 55, 0.1, 20.0, 1.2, 1.4, -30, 85),
    ("CR2025", 165, 0.2, 20.0, 2.5, 2.3, -30, 85),
    ("CR2412", 100, 0.2, 24.5, 1.2, 2.0, -30, 85),
    ("CR2477", 1000, 0.2, 24.5, 7.7, 10.5, -30, 85),
    ("CR3032", 500, 0.2, 30.0, 3.2, 6.9, -30, 85),
    ("CR2032A", 210, 0.2, 20.0, 3.2, 3.0, -40, 125),
    ("CR2032B", 210, 0.2, 20.0, 3.2, 3.0, -40, 120),
    ("CR2050A", 345, 0.2, 20.0, 5.0, 4.1, -40, 125),
    ("CR2050B2", 345, 0.2, 20.0, 5.0, 4.1, -40, 120),
    ("CR2450B", 560, 0.2, 24.5, 5.0, 6.2, -40, 105),
]

PANASONIC_BR = [
    ("BR1220", 35, 0.03, 12.5, 2.0, 0.7, -40, 85),
    ("BR1225", 48, 0.03, 12.5, 2.5, 0.8, -40, 85),
    ("BR1632", 120, 0.03, 16.0, 3.2, 1.5, -40, 85),
    ("BR2032", 200, 0.03, 20.0, 3.2, 2.6, -40, 85),
    ("BR2325", 165, 0.03, 23.0, 2.5, 3.0, -40, 85),
    ("BR2330", 255, 0.03, 23.0, 3.0, 3.2, -40, 85),
    ("BR3032", 500, 0.03, 30.0, 3.2, 5.7, -40, 85),
    ("BR1225A", 48, 0.03, 12.5, 2.5, 0.8, -40, 125),
    ("BR1632A", 120, 0.03, 16.0, 3.2, 1.5, -40, 125),
    ("BR2330A", 255, 0.03, 23.0, 3.0, 3.2, -40, 125),
    ("BR2477A", 1000, 0.03, 24.5, 7.7, 7.9, -40, 125),
]


EEMB_LP = [
    ("LP452235", 280, 5.6, "452235"),
    ("LP605590", 3400, 68, "605590"),
    ("LP652438", 540, 10.8, "652438"),
    ("LP505464", 1800, 36, "505464"),
    ("LP604765", 1900, 38, "604765"),
    ("LP702030", 350, 7, "702030"),
    ("LP404261", 1000, 20, "404261"),
    ("LP822245", 750, 15, "822245"),
    ("LP603448", 1050, 21, "603448"),
    ("LP653042", 820, 16.4, "LP653042"),
    ("LP803450", 1400, 28, "803450"),
    ("LP402535", 320, 6.4, "402535"),
    ("LP583759", 1350, 27, "583759"),
    ("LP604374", 2200, 44, "604374"),
    ("LP604040", 950, 19, "604040"),
    ("LP383450", 720, 14.4, "383450"),
    ("LP453048", 710, 14.2, "453048"),
    ("LP103395", 3700, 74, "103395"),
    ("LP103042", 1250, 25, "103042"),
    ("LP603436", 750, 15, "603436"),
    ("LP902977", 2200, 44, "902977"),
    ("LP403026", 260, 5.2, "403026"),
    ("LP752726", 450, 9, "752726"),
    ("LP503048", 750, 15, "503048"),
    ("LP553250", 950, 19, "553250"),
    ("LP602945", 800, 16, "602945"),
    ("LP503759", 1250, 25, "503759"),
    ("LP9051109", 5500, 110, "9051109"),
    ("LP902030", 500, 10, "902030"),
    ("LP803448", 1350, 27, "803448"),
    ("LP7545135", 4500, 90, "7545135"),
    ("LP722977", 1700, 34, "722977"),
    ("LP703450", 1250, 25, "703450"),
    ("LP603449", 1100, 22, "603449"),
    ("LP603048", 900, 18, "603048"),
    ("LP603030", 480, 9.6, "603030"),
    ("LP602248", 620, 12.4, "602248"),
    ("LP576167", 2500, 50, "576167"),
    ("LP562438", 500, 10, "562438"),
    ("LP552025", 170, 3.4, "552025"),
    ("LP542730", 380, 7.6, "542730"),
    ("LP524261", 1500, 30, "524261"),
    ("LP503450", 950, 19, "503450"),
    ("LP104765", 3300, 66, "104765"),
    ("LP103454", 2000, 40, "103454"),
    ("LP323450", 550, 11, "323450"),
    ("LP311620", 50, 1, "311620"),
    ("LP305884", 1400, 28, "305884"),
    ("LP305590", 1450, 29, "305590"),
    ("LP502030", 250, 5, "502030"),
    ("LP452030", 230, 4.6, "452030"),
    ("LP402030", 190, 3.8, "402030"),
    ("LP401745", 250, 5, "401745"),
    ("LP601730", 260, 5.2, "601730"),
    ("LP401730", 150, 2.8, "401730"),
    ("LP601622", 160, 3.2, "601622"),
    ("LP401429", 130, 2.6, "401429"),
    ("LP501230", 140, 2.8, "501230"),
    ("LP401230", 100, 2, "401230"),
    ("LP451124", 65, 1.3, "451124"),
]


def _panasonic(records, register, observation):
    source = {
        "uid": "src/panasonic-coin-primary-lineup-march-2026",
        "kind": "datasheet",
        "title": "Panasonic Coin type Primary Lithium Batteries",
        "url": "https://energy.panasonic.com/dam/master/pdf/en/material/lithium/Introduction_of_coin_type_primary_lithium_batteries_EN.pdf",
        "revision": "March 2026 cover; lineup tables state contents valid as of September 2022",
        "license": "proprietary",
        "redistributable": False,
        "note": "Retrieved 2026-08-16. Table-row locator quotes normalize whitespace from the PDF.",
    }
    cr_chem = _chemistry(
        "CR series Li/MnO2", "manganese dioxide", None,
        "manganese dioxide positive electrode (CR series)",
        page=2,
    )
    br_chem = _chemistry(
        "BR series primary lithium", None, None,
        "BR series Coin type Primary Lithium Batteries Line up",
        page=4,
    )
    for family, rows, page, chemistry in (("CR", PANASONIC_CR, 3, cr_chem),
                                           ("BR", PANASONIC_BR, 4, br_chem)):
        for model, cap, drain, diameter, height, mass, tmin, tmax in rows:
            row_quote = f"{model} {cap} {drain} {diameter} {height} {mass}"
            shared_temperature = ((family == "CR" and tmin == -30 and tmax == 85)
                                  or (family == "BR" and tmin == -40 and tmax == 85))
            if not shared_temperature:
                row_quote += f" {tmin} ～ {tmax}"
            obs = _physical_observations(
                observation, model=model, voltage=3, capacity_mah=cap,
                diameter=diameter, height=height, mass_g=mass, quote=row_quote,
                conditions={"unstated": ["rate_value", "rate_unit",
                                         "temperature_c", "voltage_lower_v"]},
                mass_statistic="typical",
            )
            for item in obs:
                item["locator"]["page"] = page
                if item["quantity"] == "nominal_voltage":
                    item["locator"]["quote"] = "Nominal voltage (V) 3"
            temperature_quote = (f"Operating temperature range (°C) {tmin} ～ {tmax}"
                                 if shared_temperature else row_quote)
            for quantity, value, statistic in (("operating_temperature_min", tmin, "minimum"),
                                               ("operating_temperature_max", tmax, "maximum")):
                obs.append(observation(
                    quantity, value, "°C", temperature_quote,
                    statistic=statistic, page=page,
                    conditions={"unstated": ["temperature_reference", "direction"]},
                ))
            records.append(_candidate(
                register, maker_slug="panasonic", manufacturer="Panasonic Energy",
                model=model, kind="primary_cell", rechargeable=False,
                form_factor="coin", source=source, observations=obs,
                chemistry=chemistry,
            ))


def _eemb(records, register, observation):
    source = {
        "uid": "src/eemb-lithium-polymer-standard-web-2026-08-16",
        "kind": "manufacturer_web",
        "title": "EEMB Lithium Polymer Standard Type Battery",
        "url": "https://www.eemb.com/products-55",
        "license": "proprietary",
        "redistributable": False,
        "note": "Retrieved 2026-08-16. The manufacturer Size field is preserved verbatim as form_factor_code. Its axes, units and tolerances are not stated, so no dimensional observations are inferred from it.",
    }
    chemistry = _chemistry(
        "Lithium-ion polymer", None, None,
        "Lithium-ion Polymer Battery is a type of Lithium-ion battery in foil-type (polymer laminate) case.",
    )
    for model, capacity_mah, mass_g, size_field in EEMB_LP:
        quote = f"{model} | {size_field} | {mass_g} g | 3.7 V | {capacity_mah} mAh"
        observations = [
            observation(
                "capacity", capacity_mah / 1000, "Ah", quote,
                section="Lithium Polymer Standard Type Battery product table",
                conditions={"unstated": ["rate_value", "rate_unit",
                                         "temperature_c", "voltage_lower_v"]},
            ),
            observation("nominal_voltage", 3.7, "V", quote, statistic="nominal",
                        section="Lithium Polymer Standard Type Battery product table"),
            observation("mass", mass_g, "g", quote,
                        section="Lithium Polymer Standard Type Battery product table"),
            observation(
                "operating_temperature_min", -20, "°C",
                "Operating temperature range of -20°C to +60°C", statistic="minimum",
                section="Main Features",
                conditions={"unstated": ["temperature_reference", "direction"]},
            ),
            observation(
                "operating_temperature_max", 60, "°C",
                "Operating temperature range of -20°C to +60°C", statistic="maximum",
                section="Main Features",
                conditions={"unstated": ["temperature_reference", "direction"]},
            ),
        ]
        records.append(_candidate(
            register, maker_slug="eemb", manufacturer="EEMB", model=model,
            kind="cell", rechargeable=True, form_factor="pouch",
            form_factor_code=f"EEMB Size {size_field}", source=source,
            observations=observations, chemistry=chemistry,
        ))


def build(records, register, observation):
    """Append 152 unique Maxell, Panasonic and EEMB candidates."""
    _maxell(records, register, observation)
    _panasonic(records, register, observation)
    _eemb(records, register, observation)
