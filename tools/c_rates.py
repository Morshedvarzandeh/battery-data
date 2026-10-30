"""One rule for C-rates, shared by the validator, the issue-recovery parser and
the migration.

"C" in the unit table (schema/010_vocabulary.sql) is the coulomb. A current
limit printed as "2.2C" is a multiple of capacity, so it belongs in the C-rate
quantity beside each ampere quantity (schema/138_c_rate_quantities.sql), with
unit "C-rate", and is never converted to amperes unless the source does that
arithmetic itself.
"""
from __future__ import annotations

TWIN = {
    "max_continuous_discharge_current": "max_continuous_discharge_rate",
    "max_continuous_charge_current": "max_continuous_charge_rate",
    "max_pulse_discharge_current": "max_pulse_discharge_rate",
    "standard_charge_current": "standard_charge_rate",
}
REFERENCE = "Manufacturer C-rate label; the capacity the C-rate refers to is not stated"


def is_misfiled(observation: dict) -> bool:
    return observation.get("quantity") in TWIN and observation.get("unit") == "C"


def normalize(observation: dict) -> bool:
    """Move a C-rate stored as a current to its C-rate quantity, in place.

    Returns True when it changed something. Value, conditions and locator are
    kept; the capacity basis is recorded as not stated.
    """
    if not is_misfiled(observation):
        return False
    observation["quantity"] = TWIN[observation["quantity"]]
    observation["unit"] = "C-rate"
    extra = observation.setdefault("conditions", {}).setdefault("extra", {})
    extra.setdefault("rate_reference", REFERENCE)
    return True
