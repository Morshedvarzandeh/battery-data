# Everything around the battery, and every chemistry

A pack is a cell plus the hardware that lets it be used safely: contactors,
fuses, a pyro-fuse, a BMS, busbars, sensors, an isolation monitor, a DC-DC
converter or charger, cooling plates and heaters. A reference that stops at
the cell answers half of every pack design question. And a battery reference
that stops at lithium ignores the lead-acid battery in every car, the AGM
battery in every UPS, and the sodium-ion cells now leaving the pilot lines.

This document is the scope extension. The rule does not change: **a value
without its conditions, its page and its quote is not a fact**, and the
conditions a component rating depends on are enforced the same way a cell's
are, through `quantity.required_conditions`.

---

## Components

`product.kind = 'component'` says the product is one of the parts around the
cell; `product.component_kind` says which:

| Group | `component_kind` values |
|---|---|
| Switching and protection | `contactor`, `relay`, `fuse`, `pyro_fuse`, `circuit_breaker`, `battery_disconnect_unit`, `service_disconnect`, `pre_charge_resistor` |
| Power conversion | `dc_dc_converter`, `on_board_charger`, `inverter`, `pcs` |
| Management and sensing | `bms`, `current_sensor`, `voltage_sensor`, `temperature_sensor`, `isolation_monitor` |
| Conduction and connection | `busbar`, `cell_contact_system`, `connector`, `cable`, `wire_harness` |
| Thermal and mechanical | `cooling_plate`, `chiller`, `heater`, `thermal_interface_material`, `vent`, `enclosure`, `cell_holder` |
| Electrochemical components | `electrode`, `separator`, `electrolyte` |

A component's contribution file is the same file a cell uses. Only the
quantities differ, and the conditions they need:

| Quantity | Required conditions | Why |
|---|---|---|
| `rated_current` | `temperature_c` | a carry current derates with ambient; it is a curve pretending to be a number |
| `breaking_capacity` | `circuit_voltage_v`, `time_constant_ms` | DC interruption depends on the circuit voltage and the L/R of the test circuit |
| `making_capacity` | `circuit_voltage_v` | what a contactor can close onto without welding |
| `i2t_total` | `circuit_voltage_v` | the arcing part of a fuse's clearing integral depends on voltage; `i2t_prearcing` does not |
| `minimum_breaking_current` | `circuit_voltage_v` | below it a fuse melts without clearing |
| `contact_resistance` | `rate_value`, `rate_unit` | quoted at a test current; film resistance dominates at low current |
| `electrical_endurance` | `circuit_voltage_v`, `rate_value`, `rate_unit` | operations under a stated switched load |
| `dielectric_strength` | `duration_s` | withstand voltage for a stated time |
| `insulation_resistance` | `circuit_voltage_v` | measured at a stated DC test voltage |
| `voltage_drop`, `power_dissipation` | `rate_value`, `rate_unit` | at a stated current |
| `output_current` | `temperature_c` | derates with ambient |
| `conversion_efficiency` | `circuit_voltage_v`, `rate_value`, `rate_unit` | a surface over input voltage and load; `rate_unit: pct` states the load as a fraction of rating |
| `measurement_accuracy` | `temperature_c` | sensor accuracy drifts with temperature; `extra.basis` says of reading or of full scale |

Quantities with no conditions: `rated_voltage`, `i2t_prearcing`,
`coil_voltage`, `coil_power`, `pickup_voltage`, `dropout_voltage`,
`mechanical_endurance`, `cold_resistance`, `operate_time`, `release_time`,
`input_voltage_min`, `input_voltage_max`, `output_voltage_min`,
`output_voltage_max`, `switching_frequency`, `measurement_range_max`,
`balancing_current`, `short_circuit_current`. Mass, dimensions and the
operating and storage windows apply as they do to a cell.

Two conventions worth stating outright:

- **Coil power** is the hold power unless `statistic` or `extra.phase`
  says pickup. Economiser coils differ by an order of magnitude between the
  two, and a datasheet that prints one number usually means hold.
- **Time-current characteristics** are curves, not scalars: a fuse's
  `time_current` curve carries current on x and clearing time on y, with
  the ambient and the circuit voltage as its conditions.

An illustrative contactor record, with a deliberately fictional part so no
number here can be mistaken for data:

```yaml
product:
  uid: component/example-co/ex-500
  kind: component
  component_kind: contactor
  manufacturer: Example Co.
  model_number: EX-500
observations:
  - quantity: rated_current
    statistic: rated
    value: 500
    unit: A
    conditions: {temperature_c: 85, temperature_reference: ambient}
    locator: {page: 1, quote: "..."}
  - quantity: breaking_capacity
    statistic: maximum
    value: 2000
    unit: A
    conditions: {circuit_voltage_v: 450, time_constant_ms: 1}
    locator: {page: 2, quote: "..."}
```

### Bill of materials

A pack or system names its components the way it names its cells, through
`product_assembly`: one `CONTAINS` edge per part with the quantity fitted.
That is what lets the graph answer "which fielded packs use a contactor from
supplier X", the same question it already answers for cells.

---

## Chemistry family and construction

`chemistry.designation` stays the maker's own string, because that is what
the document says. `chemistry.family` is the enum a query filters on and the
class the ontology export binds to:

`lithium_ion`, `lithium_metal`, `lithium_primary`, `sodium_ion`,
`sodium_sulfur`, `sodium_nickel_chloride`, `lead_acid`,
`nickel_metal_hydride`, `nickel_cadmium`, `nickel_zinc`, `nickel_iron`,
`zinc_air`, `zinc_carbon`, `alkaline`, `silver_oxide`, `flow_vanadium`,
`flow_zinc_bromine`, `flow_iron`, `flow_other`, `solid_state`,
`supercapacitor`, `other`.

For lead-acid, `chemistry.construction` records what decides the charge
voltages, the orientation, the gassing and the cycle life more than the
chemistry does: `flooded`, `agm`, `gel`, `tubular_plate`, `flat_plate`,
`bipolar`, `carbon_enhanced`. The database refuses a construction on any
other family.

## Lead-acid quantities

Lead-acid practice quotes things lithium practice does not, and each carries
a convention that has to travel with the number (see
`docs/02-conventions.md`, sections 28 to 33):

| Quantity | Required conditions | Convention carried |
|---|---|---|
| `capacity` | `rate_value`, `rate_unit`, `temperature_c`, `voltage_lower_v` | the 20-hour, 10-hour and 5-hour rates are separate observations, never one number |
| `cold_cranking_current` | `temperature_c`, `duration_s`, `cutoff_voltage_v` | SAE J537, EN 50342-1, DIN 43539 and JIS D 5301 differ on all three; `extra.standard` names which |
| `reserve_capacity_minutes` | `load_value`, `load_unit`, `cutoff_voltage_v`, `temperature_c` | a capacity with its load |
| `float_charge_voltage`, `cycle_charge_voltage` | `temperature_c` | two different voltages, both temperature-compensated |
| `temperature_compensation_coefficient` | none | `extra.per` says per cell or per battery |
| `calendar_life` | `temperature_c`, `soc_pct` | design life on float is calendar life at 100% SOC and the stated temperature |

## Sodium-ion

Sodium-ion cells use the lithium-ion quantities unchanged. Two things differ
and are recorded rather than assumed: the voltage window is wider and lower
(cutoffs near 1.5 V are normal), so `voltage_lower_v` on a capacity is never
optional; and several makers ship at 0 V, so `shipping_voltage` is a real
observation rather than a curiosity.

---

## Coverage

`web/data/coverage.json` carries a target list for every group above:
lead-acid and AGM, nickel and zinc, flow, supercapacitors, sodium beyond
sodium-ion, and each component class. A name on that list is a product that
exists and belongs in a reference; it becomes a number only when a document
lands through the contribution path.
