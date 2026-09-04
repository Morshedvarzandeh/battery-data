"""Official Energizer product-datasheet expansion, retrieved 2026-09-04.

The manufacturer PDF bodies are intentionally not stored.  Each record keeps
the official URL, exact form number and SHA-256 of the retrieved document so a
reviewer can identify the precise revision behind every extracted fact.
"""
from __future__ import annotations

import re


RETRIEVED = "2026-09-04"
BASE_URL = "https://data.energizer.com/pdfs"


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _obs(observation, quantity, value, unit, quote, *, statistic=None,
         conditions=None, **extra):
    return observation(
        quantity, value, unit, quote, statistic=statistic,
        conditions=conditions, page=1, **extra,
    )


def _source(item):
    return {
        "uid": f"src/energizer-{_slug(item['model'])}-{_slug(item['revision'])}",
        "kind": "datasheet",
        "title": f"Energizer {item['model']} product datasheet",
        "url": f"{BASE_URL}/{item['file']}",
        "revision": item["revision"],
        "is_final": True,
        "license": "proprietary",
        "redistributable": False,
        "sha256": item["sha256"],
        "note": (
            f"Retrieved {RETRIEVED} from Energizer's official technical-"
            "information catalog. Facts only; the PDF body is not redistributed. "
            "The manufacturer states that the sheet contains typical information, "
            "does not constitute a warranty, and is for reference only. Diagram "
            "dimension excerpts below are normalized transcriptions: labels and "
            "values are preserved while visual layout and whitespace are not."
        ),
    }


def _document(item, observations, *, kind, form_factor, rechargeable, chemistry,
              aliases=None):
    product = {
        "uid": f"{kind}/energizer/{_slug(item['model'])}",
        "kind": kind,
        "manufacturer": "Energizer",
        "model_number": item["model"],
        "form_factor": form_factor,
        "is_rechargeable": rechargeable,
    }
    if aliases:
        product["aliases"] = aliases
    return {
        "schema_version": "1",
        "product": product,
        "source": _source(item),
        "chemistry": {
            "designation": chemistry,
            "locator": {"page": 1, "quote": item["chemistry_quote"]},
        },
        "observations": observations,
    }


COIN = [
    {"model": "BR1225", "file": "BR1225GL0626.pdf", "revision": "Form No. BR1225GL0626", "sha256": "01f73fab9f71a76cf0f78926588d9a705d33e5ce070bf6ab6b30c505babb8c1f", "mass": 0.8, "volume": 0.3, "diameter": 12.5, "height": 2.5, "chemistry": "Li/CFx", "chemistry_quote": "Chemical System: Lithium / Poly-Carbon Monoflouride (Li/CFx)"},
    {"model": "CR1025", "file": "1025GL0626.pdf", "revision": "Form No. 1025GL0626", "sha256": "67492914b00d6d80e9deed7022818c3ec8b9acafa7b4fed0f9db6c21abebb2cc", "mass": 0.7, "volume": 0.2, "diameter": 10.0, "height": 2.5, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR1216", "file": "1216GL0626.pdf", "revision": "Form No. 1216GL0626", "sha256": "d612cbb9fc1427997cc6dba9150b2af061c8c217392a402691cce0db95e177f7", "mass": 0.6, "volume": 0.2, "diameter": 12.5, "height": 1.6, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR1220", "file": "1220GL0626.pdf", "revision": "Form No. 1220GL0626", "sha256": "00e663e1cd98a95ab57e2f72de427693a42da3608d6683730138e6a7a461aa8c", "mass": 0.78, "volume": 0.25, "diameter": 12.5, "height": 2.0, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR1616", "file": "1616GL0626.pdf", "revision": "Form No. 1616GL0626", "sha256": "a0356b013b78dce05fd959bf0125bc8a6eb024c0733a96a784d665c2e03792a7", "mass": 1.1, "volume": 0.32, "diameter": 16.0, "height": 1.6, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR1620", "file": "1620GL0726.pdf", "revision": "Form No. 1620GL0626", "sha256": "5eaae95c79caa1ee6b4f158d8e88fa75e76c281643abbb8592946a6c6672a5bf", "mass": 1.3, "volume": 0.4, "diameter": 16.0, "height": 2.0, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR1632", "file": "1632GL0726.pdf", "revision": "Form No. 1632GL0626", "sha256": "854cc7de0f6ee47fbdc0a0ebc0c44770d0e40a4794e1b6e5f34d0dceed80f87b", "mass": 1.8, "volume": 0.5, "diameter": 16.0, "height": 3.2, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR2012", "file": "2012GL0726.pdf", "revision": "Form No. 2012GL0626", "sha256": "0ee58d29269ba862d48c9f0efef00c3fc88295ba725b5cf3bbf55ca54566afc7", "mass": 1.3, "volume": 0.3, "diameter": 20.0, "height": 1.2, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR2016", "file": "2016GL0626.pdf", "revision": "Form No. 2016GL0626", "sha256": "f0ac0b693264d9e2d2cd9820a6e670feda63ae9af57aea8dd2582c31abf204a3", "mass": 1.9, "volume": 0.5, "diameter": 20.0, "height": 1.6, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR2025", "file": "2025GL0626.pdf", "revision": "Form No. 2025GL0626", "sha256": "73a0e169cf502937fdcc7cc93d7629f39d19613dab11b3ea043c47e2edb943cc", "mass": 2.6, "volume": 0.8, "diameter": 20.0, "height": 2.5, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR2032", "file": "2032GL0626.pdf", "revision": "Form No. 2032GL0626", "sha256": "18a8acf146ae4b549b85377e923ece87e586d51247d12bc27239f6c773cd54bd", "mass": 3.0, "volume": 1.0, "diameter": 20.0, "height": 3.2, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR2430", "file": "2430GL0726.pdf", "revision": "Form No. 2430GL0626", "sha256": "2d847291e6bcf81735c19649bf7ffa24c902ba1de17c5bf1692c21ca6f35e623", "mass": 4.6, "volume": 1.3, "diameter": 24.5, "height": 3.0, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
    {"model": "CR2450", "file": "2450GL0626.pdf", "revision": "Form No. 2450GL0626", "sha256": "f6c56c8db458497132fcdc67055126646e167c99db8b41af88db6205dd2386dc", "mass": 6.8, "volume": 2.4, "diameter": 24.5, "height": 5.0, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)"},
]


ZINC_AIR = [
    {"model": "AC10E", "file": "ENR_AC10E-1.pdf", "revision": "Form No. 10GL0824", "sha256": "17586110949ef9db55af017bec4bd9c7e9c152c93c8c1cfb94fc4ac0ea02af2d", "mass": 0.3, "volume": 0.08, "diameter": 5.8, "height": 3.6, "ansi": "7005ZD", "iec": "PR70"},
    {"model": "AC13E", "file": "ENR_AC13E-1.pdf", "revision": "Form No. 13GL0824", "sha256": "b3d35faaa1bac173261fdc38d95eea45efcaffedc5a5e1ba6f0e074e4ec1c412", "mass": 0.8, "volume": 0.3, "diameter": 7.9, "height": 5.4, "ansi": "7000ZD", "iec": "PR48"},
    {"model": "AC312E", "file": "ENR_AC312E-1.pdf", "revision": "Form No. 312GL0824", "sha256": "ff286846d0d3aa05b3ea4dba681daed9a93ab7a9838490e46c9cc7518130876d", "mass": 0.5, "volume": 0.2, "diameter": 7.9, "height": 3.6, "ansi": "7002ZD", "iec": "PR41"},
    {"model": "AC675E", "file": "ENR_AC675E-1.pdf", "revision": "Form No. 675GL0824", "sha256": "f29d4cf9bd4946b0c047e4b99c8cb1a6ba2f0f7535d50319a89e99cf3d124a8c", "mass": 1.8, "volume": 0.6, "diameter": 11.6, "height": 5.4, "ansi": "7003ZD", "iec": "PR44"},
]

for item in ZINC_AIR:
    item.update({"chemistry_quote": "Chemical System: Zinc Air (Zn/O2)"})


PRIMARY = [
    {"model": "123", "file": "123.pdf", "revision": "Form No. 123GL1018", "sha256": "372053c271933ca6bf90860086058c758dc484cb0c933cb0a0f7e56195c126f6", "form_factor": "cylindrical", "voltage": 3.0, "mass": 16.5, "volume": 7.0, "diameter": 17.0, "height": 34.5, "capacity": 1.5, "load_ohm": 100, "max_continuous_a": 1.5, "max_pulse_a": 3.5, "lithium_g": 0.55, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)", "aliases": ["EL123", "CR17345"]},
    {"model": "1CR2", "file": "1cr2gl0121.pdf", "revision": "Form No. 1CR2GL0121", "sha256": "7f27b30bfdf075d07450f6b459066804b57936ef7f687ed823ffa422c677a384", "form_factor": "cylindrical", "voltage": 3.0, "mass": 11.0, "volume": 5.2, "diameter": 15.6, "height": 27.0, "capacity": 0.8, "load_ohm": 100, "max_continuous_a": 1.0, "max_pulse_a": 2.5, "lithium_g": 0.28, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)", "aliases": ["EL1CR2", "CR2", "CR15H270"]},
    {"model": "2L76", "file": "2l76.pdf", "revision": "Form No. 2L76NA1117", "sha256": "d12aaa9b56e305f2e78bc1343a02d903d03bf200cc8ee3cf7d91237cf2206797", "form_factor": "cylindrical", "voltage": 3.0, "mass": 3.0, "volume": 1.1, "diameter": 11.6, "height": 10.8, "capacity": 0.16, "load_ohm": 15000, "max_continuous_a": 0.060, "max_pulse_a": 0.080, "lithium_g": 0.056, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium / Manganese Dioxide (Li/MnO2)", "aliases": ["CR11108"]},
    {"model": "L91", "file": "L91GL0726.pdf", "revision": "Form No. L91GL0726", "sha256": "6c89f5d45d249757270b2e2db499422712b62372a832362c2dbce259d7baace5", "form_factor": "cylindrical", "voltage": 1.5, "mass": 15.0, "volume": 8.0, "diameter": 14.5, "height": 50.5, "max_continuous_a": 2.5, "max_pulse_a": 4.0, "pulse_s": 2, "lithium_upper_g": 1.0, "chemistry": "Li/FeS2", "chemistry_quote": "Chemical System: Lithium/Iron Disulfide (Li/FeS2)", "aliases": ["FR14505", "FR6", "ANSI 15-LF"]},
    {"model": "L92", "file": "L92GL0725.pdf", "revision": "Form No. L92GL0725", "sha256": "80f739fb2388119f4cd8aba3ee1334a8c94a1c2ed22f980df464b9f2c651ae5a", "form_factor": "cylindrical", "voltage": 1.5, "mass": 7.6, "volume": 3.8, "diameter": 10.5, "height": 44.5, "max_continuous_a": 1.5, "max_pulse_a": 2.0, "pulse_s": 2, "lithium_upper_g": 1.0, "chemistry": "Li/FeS2", "chemistry_quote": "Chemical System: Lithium/Iron Disulfide (Li/FeS2)", "aliases": ["FR03", "ANSI 24-LF"]},
    {"model": "L522", "file": "l522-1119.pdf", "revision": "Form No. L522GL1119", "sha256": "0a7ae3569f46eac7862ab24917eb9cc884e015ce43f36b10d569ed8d24f535d4", "form_factor": "other", "kind": "pack", "voltage": 9.0, "mass": 33.9, "volume": 21.4, "height": 49.0, "length": 26.5, "width": 17.5, "max_continuous_a": 1.0, "lithium_g": 1.35, "chemistry": "Li/MnO2", "chemistry_quote": "Chemical System: Lithium-Manganese Dioxide (Li/MnO2)", "aliases": ["ANSI 1604LC"]},
]


NIMH = [
    {"model": "NH12-500", "file": "nh12_500gl0221.pdf", "revision": "Form No. NH12-500GL0221", "sha256": "401b62cf191a726c389c76951e5cc31558dc38ade0984cef702dc10821781f8a", "capacity": 0.5, "mass": 10.0, "volume": 3.8, "diameter": 10.5, "height": 44.5, "cutoff": None},
    {"model": "NH12-700", "file": "nh12-700.pdf", "revision": "Form No. NH12-700GL0218", "sha256": "87355866a50763c47ff799227a34f9ea3d92c52265e65a068f7a78b7f1eb9dbe", "capacity": 0.7, "mass": 11.0, "volume": 3.8, "diameter": 10.5, "height": 44.5, "cutoff": None},
    {"model": "NH12-800", "file": "nh12-800.pdf", "revision": "Form No. NH12-800GL1118", "sha256": "212f1fbbb495a85a8002f720fb149f9062c44385127f8a1e8134e0dc1e0bd707", "capacity": 0.8, "mass": 12.0, "volume": 3.8, "diameter": 10.5, "height": 44.5, "cutoff": 1.0},
    {"model": "NH15-2000", "file": "nh15-2000gl1220.pdf", "revision": "Form No. NH15-2000GL1220", "sha256": "d313803a7bf067084ac6719b804b21b0b6a413ff02818ee2cd8ec7ae4d0f35a1", "capacity": 2.0, "mass": 25.0, "volume": 8.3, "diameter": 14.5, "height": 50.5, "cutoff": 1.0},
    {"model": "NH15-2300", "file": "nh15-2300gl1220.pdf", "revision": "Form No. NH15-2300GL1220", "sha256": "68093da90245879399cda62bacbc023b82e6899e8ed2ab71f43c6b8d0f41a3fa", "capacity": 2.3, "mass": 27.0, "volume": 8.3, "diameter": 14.5, "height": 50.5, "cutoff": None},
    {"model": "NH22-175", "file": "nh22-175.pdf", "revision": "Form No. NH22-175GL1118", "sha256": "5aad5daa5e53a72128a07b98e10a5e56bcb6596c5ffac1ba6079153bdcf9c3c1", "capacity": 0.175, "mass": 42.0, "volume": 22.0, "height": 48.5, "length": 26.5, "width": 17.5, "cutoff": 1.0, "voltage": 8.4, "kind": "pack", "form_factor": "other"},
    {"model": "NH35-2500", "file": "nh35-2500.pdf", "revision": "Form No. NH35-2500GL1118", "sha256": "cfc75252da765476147fbe55b727e2ac80a7e96c3fac5fe8f1f633f6949c7005", "capacity": 2.5, "mass": 66.0, "volume": 27.0, "diameter": 26.2, "height": 50.0, "cutoff": 1.0},
    {"model": "NH50-2500", "file": "NH50-2500.pdf", "revision": "Form No. NH50-2500GL1118", "sha256": "f4fbed3a9b3c3db3f1976d9b8a0970650da40a6a2bf39a40e90de1840a40a14b", "capacity": 2.5, "mass": 73.0, "volume": 57.0, "diameter": 34.2, "height": 61.5, "cutoff": 1.0},
]


for item in NIMH:
    item.update({
        "voltage": item.get("voltage", 1.2),
        "kind": item.get("kind", "cell"),
        "form_factor": item.get("form_factor", "cylindrical"),
        "chemistry_quote": "Chemical System: Nickel-Metal Hydride (NiMH)",
    })


def _physical(observation, item):
    quote = (
        f"Industry Standard Dimensions (mm): diameter maximum "
        f"{item['diameter']:g}; height maximum {item['height']:g}"
    )
    return [
        _obs(observation, "diameter", item["diameter"], "mm", quote,
             statistic="maximum"),
        _obs(observation, "height", item["height"], "mm", quote,
             statistic="maximum"),
    ]


def _rectangular(observation, item):
    quote = (
        "Industry Standard Dimensions (mm): "
        f"height maximum {item['height']:g}; length maximum {item['length']:g}; "
        f"width maximum {item['width']:g}"
    )
    return [
        _obs(observation, "height", item["height"], "mm", quote,
             statistic="maximum"),
        _obs(observation, "length", item["length"], "mm", quote,
             statistic="maximum"),
        _obs(observation, "width", item["width"], "mm", quote,
             statistic="maximum"),
    ]


def _common(observation, item):
    return [
        _obs(observation, "nominal_voltage", item["voltage"], "V",
             f"Nominal Voltage: {item['voltage']:g} Volts", statistic="nominal"),
        _obs(observation, "mass", item["mass"], "g",
             f"Typical Weight: {item['mass']:g} grams", statistic="typical"),
        _obs(observation, "volume", item["volume"], "cm3",
             f"Typical Volume: {item['volume']:g} cubic centimeters",
             statistic="typical"),
    ]


def _temperature_range(observation, minimum, maximum, *, storage=False,
                       direction=None):
    prefix = "Storage" if storage else (direction.title() if direction else "Operating Temp")
    quote = f"{prefix}: {minimum:g}°C to {maximum:g}°C"
    if storage:
        conditions = {"unstated": ["duration_s"]}
        quantities = ("storage_temperature_min", "storage_temperature_max")
    else:
        conditions = {"direction": direction} if direction else {}
        conditions.setdefault("unstated", []).append("temperature_reference")
        if not direction:
            conditions["unstated"].append("direction")
        quantities = ("operating_temperature_min", "operating_temperature_max")
    return [
        _obs(observation, quantities[0], minimum, "°C", quote,
             statistic="minimum", conditions=conditions),
        _obs(observation, quantities[1], maximum, "°C", quote,
             statistic="maximum", conditions=conditions),
    ]


def _build_coin(records, register, observation):
    for item in COIN:
        item = {**item, "voltage": 3.0}
        observations = _common(observation, item)
        observations += _physical(observation, item)
        observations += _temperature_range(observation, -20, 60)
        records.append(register(_document(
            item, observations, kind="primary_cell", form_factor="coin",
            rechargeable=False, chemistry=item["chemistry"],
        )))


def _build_zinc_air(records, register, observation):
    for item in ZINC_AIR:
        item = {**item, "voltage": 1.45}
        observations = _common(observation, item) + _physical(observation, item)
        records.append(register(_document(
            item, observations, kind="primary_cell", form_factor="button",
            rechargeable=False, chemistry="Zn/O2",
            aliases=[f"ANSI {item['ansi']}", f"IEC {item['iec']}"],
        )))


def _build_primary(records, register, observation):
    for item in PRIMARY:
        observations = _common(observation, item)
        observations += (
            _rectangular(observation, item)
            if "length" in item else _physical(observation, item)
        )
        observations += _temperature_range(observation, -40, 60)
        observations += _temperature_range(observation, -40, 60, storage=True)
        if item.get("capacity") is not None:
            capacity_quote = (
                f"Typical Capacity: {item['capacity'] * 1000:g} mAh (to 2.0 volts); "
                f"Rated at {item['load_ohm']:g} ohms at 21°C"
            )
            observations.append(_obs(
                observation, "capacity", item["capacity"], "Ah", capacity_quote,
                statistic="typical", conditions={
                    "rate_value": item["load_ohm"], "rate_unit": "ohm",
                    "temperature_c": 21, "voltage_lower_v": 2.0,
                },
            ))
        observations.append(_obs(
            observation, "max_continuous_discharge_current",
            item["max_continuous_a"], "A",
            f"Max Discharge: {item['max_continuous_a']:g} A continuous",
            statistic="maximum", conditions={"unstated": ["temperature_c"]},
        ))
        if item.get("max_pulse_a") is not None:
            pulse_s = item.get("pulse_s")
            conditions = {"unstated": ["temperature_c"]}
            if pulse_s is None:
                conditions["unstated"].append("pulse_duration_s")
            else:
                conditions["pulse_duration_s"] = pulse_s
            observations.append(_obs(
                observation, "max_pulse_discharge_current", item["max_pulse_a"],
                "A", f"Max Discharge: {item['max_pulse_a']:g} A pulse"
                + (f" ({pulse_s} sec on / 8 sec off)" if pulse_s else ""),
                statistic="maximum", conditions=conditions,
            ))
        if item.get("lithium_g") is not None:
            observations.append(_obs(
                observation, "lithium_content", item["lithium_g"], "g",
                f"Typical Li Content: {item['lithium_g']:g} grams",
                statistic="typical",
            ))
        if item.get("lithium_upper_g") is not None:
            observations.append(_obs(
                observation, "lithium_content", item["lithium_upper_g"], "g",
                "Lithium Content: Less than 1 gram", statistic="maximum",
                is_upper_bound=True,
            ))
        records.append(register(_document(
            item, observations, kind=item.get("kind", "primary_cell"),
            form_factor=item["form_factor"], rechargeable=False,
            chemistry=item["chemistry"], aliases=item.get("aliases"),
        )))


def _build_nimh(records, register, observation):
    for item in NIMH:
        observations = _common(observation, item)
        observations += (
            _rectangular(observation, item)
            if "length" in item else _physical(observation, item)
        )
        capacity_conditions = {
            "rate_value": 0.2, "rate_unit": "C", "temperature_c": 21,
        }
        cutoff_text = ""
        if item["cutoff"] is None:
            capacity_conditions["unstated"] = ["voltage_lower_v"]
        else:
            capacity_conditions["voltage_lower_v"] = item["cutoff"]
            cutoff_text = f" to {item['cutoff']:g} volts"
        observations.append(_obs(
            observation, "capacity", item["capacity"], "Ah",
            f"Rated Capacity: {item['capacity'] * 1000:g} mAh{cutoff_text} at 21°C; "
            "based on 0.2C discharge rate",
            statistic="rated", conditions=capacity_conditions,
        ))
        observations += _temperature_range(
            observation, 0, 40, direction="charge"
        )
        observations += _temperature_range(
            observation, 0, 50, direction="discharge"
        )
        observations += _temperature_range(
            observation, -20, 30, storage=True
        )
        records.append(register(_document(
            item, observations, kind=item["kind"],
            form_factor=item["form_factor"], rechargeable=True,
            chemistry="NiMH", aliases=item.get("aliases"),
        )))


def build(records, register, observation):
    _build_coin(records, register, observation)
    _build_zinc_air(records, register, observation)
    _build_primary(records, register, observation)
    _build_nimh(records, register, observation)
