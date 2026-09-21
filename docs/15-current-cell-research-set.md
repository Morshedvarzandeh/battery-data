# Current cell research set v1

This collection gives reviewers a bounded set of **40 current cell candidates**
instead of mixing recent products into the much larger historical queue. It covers
LG Energy Solution, EVE Energy, CATL, CALB, HiNa Battery, HiTHIUM and WeLion.

The machine-readable collection is
[`collections/current-cell-research-set-v1.json`](../collections/current-cell-research-set-v1.json).
Every entry points to its candidate record and therefore to the primary source,
observation locator, units, conditions and explicit gaps.

## Review boundary

- Status: `pending_review`
- Use: market screening and evidence review
- Excluded from: the accepted catalog, hosted API and Design cell library
- Inclusion does not confirm current availability, orderability or design suitability.
- A reviewer must approve the underlying candidate through the normal acceptance
  workflow before it can enter the accepted library.

The set deliberately excludes the CALB L173F314 regulatory draft and WeLion trial
cells whose sources say they are not final. It also avoids counting a press
announcement as a datasheet. Values with unstated test conditions remain visibly
unstated in their candidate records.

## Coverage

| Segment | Models | Main review question |
|---|---:|---|
| High-energy EV pouch/prismatic | 9 | Are electrical limits and test conditions sufficient for comparison? |
| High-power cylindrical | 5 | Are rate, thermal and cutoff conditions stated in a final manufacturer document? |
| LFP stationary storage | 11 | Are cycle-life claims tied to rate, temperature, depth of discharge and end-of-life? |
| Large-format stationary storage | 4 | Is the published name an orderable cell identity, and is chemistry stated? |
| Sodium-ion | 5 | Are commercial identity, voltage limits and test protocols complete? |
| Semi-solid electrolyte | 6 | Does a final document support the electrical and mechanical limits? |

## Promotion gate

A candidate can be accepted only when its record passes the repository schema,
duplicate checks and evidence review. Reviewers must confirm the exact model
identity, final source status, every observation locator, units and test
conditions. Missing data stays missing; it is not reconstructed from a related
model or marketing graphic.
