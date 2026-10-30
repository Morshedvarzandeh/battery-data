"""Technology and chemistry: every accepted label filed, the two never mixed."""
from __future__ import annotations

import glob
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import yaml  # noqa: E402
import classification as cls  # noqa: E402

TAX = cls.load(str(ROOT / "web" / "data" / "technologies-and-chemistries.json"))


def labels():
    out = []
    for f in glob.glob(str(ROOT / "contrib" / "**" / "*.y*ml"), recursive=True):
        raw = open(f, encoding="utf-8").read()
        d = json.loads(raw) if raw.lstrip().startswith("{") else yaml.safe_load(raw)
        if d["product"]["kind"] == "component":
            continue
        c = d.get("chemistry") or {}
        out.append((c.get("designation"), c.get("cathode_text"), c.get("electrolyte_text")))
    return out


class Classification(unittest.TestCase):
    def test_every_accepted_label_is_filed(self):
        self.assertEqual(cls.check(TAX, labels()), [])

    def test_an_unfiled_designation_stops_the_build(self):
        errs = cls.check(TAX, labels() + [("Zinc-bromine flow", None, None)])
        self.assertTrue(any("'Zinc-bromine flow'" in e and "no technology" in e for e in errs), errs)
        errs = cls.check(TAX, [("Sodium-ion", "XYZ", None)])
        self.assertTrue(any("cathode 'XYZ'" in e for e in errs), errs)

    def test_technology_and_chemistry_are_different_lists(self):
        techs = {t["name"] for t in TAX["technologies"]}
        variants = {v["name"] for t in TAX["technologies"] for v in t.get("variants", [])}
        chems = {c["name"] for c in TAX["chemistries"]}
        self.assertFalse(techs & chems, "a technology may not also be a chemistry")
        self.assertFalse(variants & chems, "a technology variant may not also be a chemistry")
        self.assertIn("Lead-acid", techs)
        self.assertTrue({"AGM", "Gel", "Flooded"} <= variants)
        self.assertTrue({"LFP", "NMC / NCM", "NCA", "NFPP"} <= chems)

    def test_classify_reads_designation_then_cathode_then_electrolyte(self):
        self.assertEqual(cls.classify(TAX, "Sodium-ion", "NFPP"), {"tech": "Sodium-ion", "variant": None, "chem": "NFPP"})
        self.assertEqual(cls.classify(TAX, "Sodium-ion", None), {"tech": "Sodium-ion", "variant": None, "chem": None})
        self.assertEqual(cls.classify(TAX, "LFP", "Lithium iron phosphate"), {"tech": "Lithium-ion", "variant": None, "chem": "LFP"})
        self.assertEqual(cls.classify(TAX, "Lithium polymer"), {"tech": "Lithium-ion", "variant": "Lithium polymer", "chem": None})
        self.assertEqual(cls.classify(TAX, "NMC+", "NMC+", "Semi-Solid-State")["variant"], "Semi-solid")
        self.assertEqual(cls.classify(TAX, "CR series Li/MnO2")["tech"], "Lithium primary")
        self.assertEqual(cls.classify(TAX, None), {"tech": None, "variant": None, "chem": None})

    def test_lead_acid_is_filed_and_never_offered_to_design(self):
        for label, variant in (("Lead-acid AGM", "AGM"), ("Lead-acid gel", "Gel"),
                               ("Lead-acid flooded", "Flooded"), ("Lead-acid EFB", "EFB")):
            self.assertEqual(cls.classify(TAX, label), {"tech": "Lead-acid", "variant": variant, "chem": "PbO2/Pb"})
        self.assertFalse(cls.designable(TAX, "Lead-acid"))
        self.assertTrue(cls.designable(TAX, "Lithium-ion") and cls.designable(TAX, "Sodium-ion"))
        self.assertTrue(cls.designable(TAX, None), "an unstated technology is not excluded on a guess")
        self.assertFalse(cls.designable(TAX, None, rechargeable=False), "a primary cell is not lithium-ion")
        self.assertEqual([t["name"] for t in TAX["technologies"] if t["design"]], ["Lithium-ion", "Sodium-ion"])
        broken = {**TAX, "technologies": [{k: v for k, v in t.items() if k != "design"} for t in TAX["technologies"]]}
        self.assertTrue(any("design: true or false" in e for e in cls.check(broken, [])))

    def test_pb_is_not_a_search_word(self):
        words = {cls.normalize(a) for e in TAX["technologies"] + TAX["chemistries"] for a in e["aliases"]}
        words |= {cls.normalize(a) for t in TAX["technologies"] for v in t.get("variants", []) for a in v["aliases"]}
        self.assertNotIn("pb", words)
        self.assertIn("na", words)
        self.assertIn("agm", words)


if __name__ == "__main__":
    unittest.main()
