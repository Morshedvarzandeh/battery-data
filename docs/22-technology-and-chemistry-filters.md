# Technology and chemistry — two filters, never one list

A record prints one chemistry label, and those labels mix two levels:
"Sodium-ion" names a battery technology, "LFP" an electrode chemistry,
"Lithium polymer" a lithium-ion construction, "Li/MnO2" a primary couple. The
finder used to list them all in one Chemistry menu, so sodium-ion sat next to
LFP and lead-acid had nowhere to go.

`web/data/technologies-and-chemistries.json` keeps them apart:

| Filter | Holds | Examples |
|---|---|---|
| **Technology** | the battery system, with its variants | Lithium-ion (Lithium polymer, Semi-solid, Solid-state) · Sodium-ion · Lead-acid (AGM, Gel, Flooded, EFB) · Nickel-metal hydride · Nickel-cadmium · Lithium primary · Alkaline · Zinc-air · Silver oxide |
| **Chemistry** | the electrode chemistry, or a primary cell's couple | LFP · LMFP · NMC / NCM · NCMA · NCA · LCO · LMO · LTO · NFPP · NFM · NVP · Prussian blue · Li/MnO2 · Li/CFx · Zn/MnO2 · Zn/O2 · Ag2O/Zn · PbO2/Pb |

Both are derived from what the record states — `chemistry.designation` first,
then `cathode_text` (a sodium-ion sheet's NFPP), then `electrolyte_text` (a
semi-solid lithium-ion cell). Nothing is written back into a record, and a
record that states no chemistry stays "Not stated" in both filters; it is
never classified from its maker or model name.

`tools/build_web_data.py` checks the file on every build: each designation in
`contrib/` must belong to exactly one technology, and a technology-level label
that prints a cathode must have that cathode filed under a chemistry. A new
label therefore stops the build until a person files it.

## Search

Each entry lists the words a reader may type. A word that names a class
matches by class, never as a substring, so `na` finds sodium-ion cells and not
Panasonic, `lead acid` and `AGM` find lead-acid, `LiFePO4` finds LFP and `li`
finds every lithium technology. Every other word is matched as a substring, as
before. `pb` is deliberately not a search word: the sodium-ion sheets print PB
for Prussian blue.

## Classes with no records yet

Nickel-cadmium, solid-state lithium-ion and several chemistries are listed
with a count of zero rather than hidden. (Lead-acid was in this list until
the first 97 lead-acid batteries arrived; see
[docs/23](23-lead-acid-batteries.md).) Choosing one shows "The library has no … records
yet" with a link to ask for them. The eight Energizer NiMH cells in the
review queue will appear under Nickel-metal hydride once accepted.

## Which technologies Lemonergy Design may use

Each technology carries `"design": true` or `false`. Only lithium-ion and
sodium-ion are `true`; the build refuses a technology that says neither.
[docs/23](23-lead-acid-batteries.md) explains how the flag is used.
