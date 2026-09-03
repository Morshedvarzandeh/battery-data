#!/usr/bin/env python3
"""
OPTIMADE-style filter grammar -> parameterised SQL.

Why borrow OPTIMADE's grammar rather than invent one: it is already the
filter language 21 materials-science providers implement, it has a
published formal definition, and it covers exactly the shape of query
this database needs - numeric comparison, boolean composition, string
matching, and list membership.

    capacity_ah >= 4.5 AND form_factor_code = "21700"
    manufacturer CONTAINS "Samsung" AND max_cont_discharge_a > 9
    elements HAS ALL "Li","Fe","P"
    chemistry = "LFP" AND (temperature_c >= 45 OR cycle_life > 5000)
    internal_resistance_dc IS KNOWN AND pulse_duration_s = 10

Everything is emitted as parameterised SQL. No user string ever reaches
the query text, so the injection surface is the identifier whitelist
alone - and unknown identifiers are rejected with a suggestion rather
than silently interpolated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------
# Field whitelist. An identifier not in here is an error, never a
# pass-through. `_bd_` prefixed names are this provider's vendor
# extensions, following OPTIMADE's `_<providerprefix>_<field>` convention.
# ---------------------------------------------------------------------
FIELDS: dict[str, dict] = {
    # product identity
    "product_uid":        {"col": "product_uid",        "type": "string"},
    "manufacturer":       {"col": "manufacturer",       "type": "string"},
    "model_number":       {"col": "model_number",       "type": "string"},
    "form_factor":        {"col": "form_factor",        "type": "string"},
    "form_factor_code":   {"col": "form_factor_code",   "type": "string"},
    "chemistry":          {"col": "chemistry",          "type": "string"},
    "cathode":            {"col": "cathode_text",       "type": "string"},
    "anode":              {"col": "anode_text",         "type": "string"},
    # performance
    "capacity_ah":        {"col": "capacity_low_rate_ah", "type": "number"},
    "capacity_1c_ah":     {"col": "capacity_1c_ah",     "type": "number"},
    "max_cont_discharge_a": {"col": "max_cont_discharge_a", "type": "number"},
    "nominal_voltage_v":  {"col": "nominal_voltage_v",  "type": "number"},
    "specific_energy_wh_kg": {"col": "specific_energy_wh_per_kg_derived",
                              "type": "number"},
    "mass_kg":            {"col": "mass_kg",            "type": "number"},
    "discharge_temp_min_c": {"col": "discharge_temp_min_c", "type": "number"},
    "discharge_temp_max_c": {"col": "discharge_temp_max_c", "type": "number"},
    "max_cont_charge_a":   {"col": "max_cont_charge_a",   "type": "number"},
    "standard_charge_a":   {"col": "standard_charge_a",   "type": "number"},
    "charge_cutoff_v":     {"col": "charge_cutoff_v",     "type": "number"},
    "discharge_cutoff_v":  {"col": "discharge_cutoff_v",  "type": "number"},
    # resistance never travels without its method: the pulse duration or the
    # frequency is filterable alongside the number
    "dcir_mohm":           {"col": "dcir_mohm",           "type": "number"},
    "dcir_pulse_s":        {"col": "dcir_pulse_s",        "type": "number"},
    "dcir_soc_pct":        {"col": "dcir_soc_pct",        "type": "number"},
    "dcir_temp_c":         {"col": "dcir_temp_c",         "type": "number"},
    "acir_mohm":           {"col": "acir_mohm",           "type": "number"},
    "acir_frequency_hz":   {"col": "acir_frequency_hz",   "type": "number"},
    # cycle life with the conditions the claim was made under
    "cycle_life_cycles":   {"col": "cycle_life_cycles",   "type": "number"},
    "cycle_life_dod_pct":  {"col": "cycle_life_dod_pct",  "type": "number"},
    "cycle_life_rate_value": {"col": "cycle_life_rate_value", "type": "number"},
    "cycle_life_rate_unit": {"col": "cycle_life_rate_unit", "type": "string"},
    "cycle_life_temp_c":   {"col": "cycle_life_temp_c",   "type": "number"},
    # vendor extensions
    "_bd_revision":       {"col": "revision_label",     "type": "string"},
    "_bd_capacity_statistic": {"col": "capacity_low_rate_statistic",
                               "type": "string"},
    "_bd_capacity_rate_c": {"col": "capacity_low_rate_c", "type": "number"},
}

# The hardware around the cell is selected on other figures, each carrying
# the condition it was stated at (see bd.v_component_selection).
COMPONENT_FIELDS: dict[str, dict] = {
    "product_uid":        {"col": "product_uid",        "type": "string"},
    "manufacturer":       {"col": "manufacturer",       "type": "string"},
    "model_number":       {"col": "model_number",       "type": "string"},
    "component_kind":     {"col": "component_kind",     "type": "string"},
    "rated_voltage_v":    {"col": "rated_voltage_v",    "type": "number"},
    "rated_current_a":    {"col": "rated_current_a",    "type": "number"},
    "rated_current_temp_c": {"col": "rated_current_temp_c", "type": "number"},
    "breaking_capacity_a": {"col": "breaking_capacity_a", "type": "number"},
    "breaking_circuit_v": {"col": "breaking_circuit_v", "type": "number"},
    "breaking_time_constant_ms": {"col": "breaking_time_constant_ms", "type": "number"},
    "i2t_prearcing_a2s":  {"col": "i2t_prearcing_a2s",  "type": "number"},
    "coil_voltage_v":     {"col": "coil_voltage_v",     "type": "number"},
    "coil_power_w":       {"col": "coil_power_w",       "type": "number"},
    "contact_resistance_mohm": {"col": "contact_resistance_mohm", "type": "number"},
    "contact_test_current_a": {"col": "contact_test_current_a", "type": "number"},
    "mechanical_endurance": {"col": "mechanical_endurance", "type": "number"},
    "input_voltage_min_v": {"col": "input_voltage_min_v", "type": "number"},
    "input_voltage_max_v": {"col": "input_voltage_max_v", "type": "number"},
    "output_voltage_min_v": {"col": "output_voltage_min_v", "type": "number"},
    "output_voltage_max_v": {"col": "output_voltage_max_v", "type": "number"},
    "output_current_a":   {"col": "output_current_a",   "type": "number"},
    "efficiency":         {"col": "efficiency",         "type": "number"},
    "efficiency_input_v": {"col": "efficiency_input_v", "type": "number"},
    "switching_frequency_hz": {"col": "switching_frequency_hz", "type": "number"},
    "mass_kg":            {"col": "mass_kg",            "type": "number"},
    "_bd_revision":       {"col": "revision_label",     "type": "string"},
}

COMPARISON = {"=": "=", "!=": "<>", "<": "<", "<=": "<=", ">": ">", ">=": ">="}


class FilterError(ValueError):
    """Raised with a message intended to be returned to the caller."""


# ---------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------
TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<string>"(?:[^"\\]|\\.)*")
  | (?P<number>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
  | (?P<op><=|>=|!=|=|<|>)
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<comma>,)
  | (?P<word>[A-Za-z_][A-Za-z0-9_]*)
""", re.VERBOSE)

KEYWORDS = {"AND", "OR", "NOT", "CONTAINS", "STARTS", "ENDS", "WITH",
            "IS", "KNOWN", "UNKNOWN", "HAS", "ALL", "ANY", "ONLY", "LENGTH"}


@dataclass
class Token:
    kind: str
    value: Any
    pos: int


def tokenize(s: str) -> list[Token]:
    toks, i = [], 0
    while i < len(s):
        m = TOKEN_RE.match(s, i)
        if not m:
            raise FilterError(f"unexpected character {s[i]!r} at position {i}")
        i = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        val = m.group()
        if kind == "string":
            val = val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        elif kind == "number":
            val = float(val) if ("." in val or "e" in val.lower()) else int(val)
        elif kind == "word" and val.upper() in KEYWORDS:
            kind, val = "keyword", val.upper()
        toks.append(Token(kind, val, m.start()))
    return toks


# ---------------------------------------------------------------------
# Recursive-descent parser  ->  (sql_fragment, params)
#
#   expr    := term   ( OR term )*
#   term    := factor ( AND factor )*
#   factor  := NOT factor | '(' expr ')' | predicate
# ---------------------------------------------------------------------
class Parser:
    def __init__(self, tokens: list[Token], fields=None):
        self.t, self.i, self.params = tokens, 0, []
        self.fields = fields or FIELDS

    # -- helpers ------------------------------------------------------
    def peek(self) -> Token | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self) -> Token:
        if self.i >= len(self.t):
            raise FilterError("unexpected end of filter")
        self.i += 1
        return self.t[self.i - 1]

    def accept_kw(self, kw: str) -> bool:
        tok = self.peek()
        if tok and tok.kind == "keyword" and tok.value == kw:
            self.i += 1
            return True
        return False

    def expect_kw(self, kw: str) -> None:
        if not self.accept_kw(kw):
            got = self.peek()
            raise FilterError(f"expected {kw}, got {got.value if got else 'end'}")

    def bind(self, value: Any) -> str:
        self.params.append(value)
        return f"${len(self.params)}"

    # -- grammar ------------------------------------------------------
    def parse(self) -> tuple[str, list]:
        sql = self.expr()
        if self.i < len(self.t):
            raise FilterError(
                f"unexpected {self.t[self.i].value!r} at position {self.t[self.i].pos}")
        return sql, self.params

    def expr(self) -> str:
        sql = self.term()
        while self.accept_kw("OR"):
            sql = f"({sql} OR {self.term()})"
        return sql

    def term(self) -> str:
        sql = self.factor()
        while self.accept_kw("AND"):
            sql = f"({sql} AND {self.factor()})"
        return sql

    def factor(self) -> str:
        if self.accept_kw("NOT"):
            return f"(NOT {self.factor()})"
        tok = self.peek()
        if tok and tok.kind == "lparen":
            self.next()
            sql = self.expr()
            close = self.next()
            if close.kind != "rparen":
                raise FilterError("unbalanced parenthesis")
            return f"({sql})"
        return self.predicate()

    def predicate(self) -> str:
        tok = self.next()
        if tok.kind != "word":
            raise FilterError(f"expected a field name, got {tok.value!r}")
        name = tok.value
        if name not in self.fields:
            raise FilterError(
                f"unknown field {name!r}. "
                f"Did you mean one of: {', '.join(_suggest(name, fields=self.fields))}?")
        col = self.fields[name]["col"]
        ftype = self.fields[name]["type"]

        nxt = self.peek()
        if nxt is None:
            raise FilterError(f"field {name!r} is not followed by an operator")

        # field <op> value
        if nxt.kind == "op":
            op = COMPARISON[self.next().value]
            v = self.next()
            if v.kind not in ("string", "number"):
                raise FilterError(f"expected a value after {op}, got {v.value!r}")
            _typecheck(name, ftype, v)
            return f"{col} {op} {self.bind(v.value)}"

        if nxt.kind != "keyword":
            raise FilterError(f"expected an operator after {name!r}, "
                              f"got {nxt.value!r}")

        kw = self.next().value

        # field IS KNOWN | IS UNKNOWN
        if kw == "IS":
            k = self.next()
            if k.kind != "keyword" or k.value not in ("KNOWN", "UNKNOWN"):
                raise FilterError("expected KNOWN or UNKNOWN after IS")
            return f"{col} IS {'NOT NULL' if k.value == 'KNOWN' else 'NULL'}"

        # field CONTAINS / STARTS WITH / ENDS WITH "s"
        if kw in ("CONTAINS", "STARTS", "ENDS"):
            if kw in ("STARTS", "ENDS"):
                self.expect_kw("WITH")
            v = self.next()
            if v.kind != "string":
                raise FilterError(f"{kw} requires a quoted string")
            pat = {"CONTAINS": f"%{v.value}%",
                   "STARTS": f"{v.value}%",
                   "ENDS": f"%{v.value}"}[kw]
            return f"{col} ILIKE {self.bind(pat)}"

        # field HAS [ALL|ANY|ONLY] v1, v2, ...
        if kw == "HAS":
            mode = "ANY"
            for m in ("ALL", "ANY", "ONLY"):
                if self.accept_kw(m):
                    mode = m
                    break
            values = [self.next().value]
            while self.peek() and self.peek().kind == "comma":
                self.next()
                values.append(self.next().value)
            p = self.bind(values)
            if mode == "ALL":
                return f"{col} @> {p}"
            if mode == "ONLY":
                return f"({col} <@ {p} AND {col} && {p})"
            return f"{col} && {p}"

        raise FilterError(f"unsupported operator {kw!r} for field {name!r}")


def _typecheck(name: str, ftype: str, tok: Token) -> None:
    if ftype == "number" and tok.kind != "number":
        raise FilterError(f"field {name!r} is numeric; "
                          f"{tok.value!r} is a string")
    if ftype == "string" and tok.kind != "string":
        raise FilterError(f"field {name!r} is a string; quote the value "
                          f'as "{tok.value}"')


def _suggest(name: str, n: int = 3, fields=None) -> list[str]:
    """Cheap edit-distance suggestion so a typo is a helpful error."""
    def dist(a: str, b: str) -> int:
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                               prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]
    return sorted(fields or FIELDS, key=lambda f: dist(name.lower(), f.lower()))[:n]


def parse_filter(expr: str, fields: dict | None = None) -> tuple[str, list]:
    """Return (SQL WHERE fragment with $1..$n placeholders, params)."""
    if not expr or not expr.strip():
        return "TRUE", []
    return Parser(tokenize(expr), fields).parse()


def to_psycopg(sql: str, params: list) -> tuple[str, list]:
    """Convert $1..$n placeholders to psycopg's %s, preserving order."""
    order: list[int] = []

    def sub(m):
        idx = int(m.group(1))
        order.append(idx)
        return "%s"

    out = re.sub(r"\$(\d+)", sub, sql)
    return out, [params[i - 1] for i in order]


# ---------------------------------------------------------------------
if __name__ == "__main__":
    CASES = [
        ('capacity_ah >= 4.5 AND form_factor_code = "21700"', True),
        ('manufacturer CONTAINS "Samsung"', True),
        ('chemistry = "LFP" AND (nominal_voltage_v < 3.4 OR capacity_ah > 200)', True),
        ('NOT form_factor = "coin"', True),
        ('capacity_ah IS KNOWN AND max_cont_discharge_a > 9', True),
        ('model_number STARTS WITH "INR"', True),
        ('_bd_capacity_statistic = "rated"', True),
        # failures, each with a useful message
        ('capacity_ah >= "4.5"', False),      # type error
        ('capcity_ah >= 4.5', False),         # typo -> suggestion
        ('capacity_ah >= 4.5 AND', False),    # truncated
        ('capacity_ah >= 4.5)', False),       # unbalanced
        ('DROP TABLE bd.observation', False), # not a field
        ("model_number = \"x'; DROP TABLE bd.product; --\"", True),  # parameterised
    ]
    ok = True
    print("OPTIMADE-style filter grammar\n" + "=" * 70)
    for expr, should_pass in CASES:
        try:
            sql, params = parse_filter(expr)
            passed = True
            detail = f"{sql}   params={params}"
        except FilterError as e:
            passed = False
            detail = str(e)
        mark = "ok  " if passed == should_pass else "FAIL"
        if passed != should_pass:
            ok = False
        print(f"\n  {mark} {expr}\n       -> {detail}")
    print("\n" + "=" * 70)
    print("PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
