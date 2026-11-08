# `top.net` analysis for a structural-Verilog simulation

Inputs (read-only): `Cache/CNN_74xx_System/output/top.net` (KiCad 10.0.4 export,
2026-11-07T23:23:23, design *74-Series 28x28 MNIST CNN - 12-Board Backplane System*,
rev 2.0), symbol libraries from `C:\Program Files\KiCad\10.0\share\kicad\symbols`,
model images from `Cache/CNN_74xx_System/model/`.

Outputs written here: `parts.csv`, `pins.json`, `nets.csv`, `memories.csv`,
`stats.json`, plus the scripts that regenerate and verify them
(`build_analysis.py`, `validate.py`).

---

## 1. Headline numbers

| quantity | value |
|---|---|
| components | 1329 |
| distinct `libsource` parts | 37 |
| sheets in the hierarchy | 33 |
| nets | 4510 |
| pin nodes (net-list pins) | 17654 |
| nets with 1 node | 667 (641 `unconnected-*` + 26 named) |
| nets with >1 driver | 85 |
| nets with no logic driver | 46 |
| parts modelled (logic/memory/clock/switch) | 24 types / 898 packages |
| parts dropped (passives, connectors, power) | 13 types / 431 packages |
| memory devices | 71 (52x 27C512, 12x 28C256, 7x HY6264AxP) |

Component counts per sheet are in `stats.json` (`by_sheet`); the largest sheets are
`B04_S07_Conv1` (154) and `B06_S08_Conv2` (154), followed by `B08_S09_FC1` /
`B09_S09_FC2` (142 each) and `B03_S04_Memories` (131).

## 2. Component inventory (`parts.csv`)

All parts in `parts.csv` need a behavioural model; the `model_kind` column says
which kind. Sorted by count:

| part | lib | n | kind | package | pins |
|---|---|---|---|---|---|
| 74HC157 | 74xx | 200 | logic - quad 2:1 mux | DIP-16 | 16 |
| 74HC283 | 74xx | 184 | logic - 4-bit adder | DIP-16 | 16 |
| 74HCT574 | 74xx | 75 | logic - octal D-FF, 3-state | DIP-20 | 20 |
| 74HC161 | 74xx | 61 | logic - 4-bit counter | DIP-16 | 16 |
| 27C512 | Memory_EPROM | 52 | ROM (64Kx8) + init image | DIP-28 | 28 |
| 74HCT541 | 74xx | 52 | logic - octal buffer, 3-state | DIP-20 | 20 |
| 74HC08 | 74xx | 49 | logic - quad AND | DIP-14 | 14 |
| 74HC32 | 74xx | 40 | logic - quad OR | DIP-14 | 14 |
| 74HC688 | 74xx | 36 | logic - 8-bit identity comparator | DIP-20 | 20 |
| 74HCT273 | 74xx | 32 | logic - octal D-FF, async reset | DIP-20 | 20 |
| 74HC04 | 74xx | 24 | logic - hex inverter | DIP-14 | 14 |
| 74HC74 | 74xx | 19 | logic - dual D-FF | DIP-14 | 14 |
| 74HC138 | 74xx | 17 | logic - 3:8 decoder | DIP-16 | 16 |
| 28C256 | Memory_EEPROM | 12 | EEPROM (32Kx8), runtime-loaded | DIP-28 | 28 |
| 74HC85 | 74xx | 12 | logic - 4-bit magnitude comparator | DIP-16 | 16 |
| 74HC00 | 74xx | 9 | logic - quad NAND | DIP-14 | 14 |
| HY6264AxP | Memory_RAM | 7 | SRAM (8Kx8), volatile | DIP-28 | 28 |
| 74HC245 | 74xx | 6 | logic - octal transceiver | DIP-20 | 20 |
| 74LS148 | 74xx | 4 | logic - 8:3 priority encoder | DIP-16 | 16 |
| 74HC238 | 74xx | 2 | logic - 3:8 decoder | DIP-16 | 16 |
| 74HC02 | 74xx | 2 | logic - quad NOR | DIP-14 | 14 |
| 74HCT245 | 74xx | 1 | logic - octal transceiver | DIP-20 | 20 |
| SW_Push | Switch | 1 | push button (stimulus) | - | 2 |
| ASE-xxxMHz | Oscillator | 1 | 8.000 MHz clock can (clock source) | - | 4 |

Pin counts were checked against the package implied by the footprint: every DIP
part matches (`pin_count_check = ok`), i.e. 74HC157=16, 74HCT541=20, 74HC688=20,
74HC85=16, 74HC161=16, 74HC283=16, 74HC245/74HCT245=20, 27C512/28C256/6264=28,
74HC00/02/04/08/32/74=14, 74HC138/238/148=16. Non-DIP parts (R, C, LED, test
points, connectors, switch, oscillator) are marked `n/a (no DIP footprint)`.

## 3. Pin maps (`pins.json`)

`pins.json` is keyed `lib:part -> pin number -> {name, etype, unit, unit_name,
lib_unit, graphic?}` and covers every modelled part, power pins included.

* `unit`/`unit_name` come from the component `units` blocks of the netlist, i.e.
  how the part is actually instantiated (A=1, B=2, ...). They were checked to be
  identical for every instance of a part (no `unit_conflicts`).
* `lib_unit` is the unit inside the KiCad symbol; `0` means "common body".
* `graphic` is present when the symbol draws something other than a plain line
  (`inverted`, `clock`, `inverted_clock`). **This is the only place polarity
  information survives** - see §6.

Every pin map was compared pin-by-pin with the library symbol (resolving
`extends`) and there are **zero name mismatches and zero electrical-type
mismatches** across all 37 parts. Spot checks done by hand:

| part | symbol | library pins | netlist pins | spot check |
|---|---|---|---|---|
| 74HC157 | `74LS157` (alias) | 16 | 16 | p1 `S` in, p4 `Za` out, p8 GND, p15 `E` in (inverted), p16 VCC |
| 74HCT541 | `74LS541` via `extends` | 20 | 20 | p1 `G1` in (inverted), p10 GND, p11 `Y7` tri-state, p19 `G2`, p20 VCC |
| 27C512 | `Memory_EPROM:27C512` | 28 | 28 | p1 `A15`, p10 `A0`, p11 `D0`, p14 GND, p20 `~CE`, p22 `~OE`, p28 VCC |
| 28C256 | `Memory_EEPROM:28C256` | 28 | 28 | p20 `~CS`, p22 `~OE`, p27 `~WE`, p28 VCC |
| HY6264AxP | `Memory_RAM:HY6264AxP` | 28 | 28 | p1 `NC`, p20 `~CS1`, p22 `~OE`, p26 `CS2`, p27 `~WE` |
| 74HC00 | `74LS00` | 14 | 14 | unit A = 1,2 in / 3 out (inverted), unit E = 14 VCC / 7 GND |

Multi-unit handling: 74HC00/02/04/08/32 use 4 gate units + a power unit (A..E);
74HC04 uses 6 inverter units + power (A..G); 74HC74 uses 2 FF units + power
(A..C). All other parts are single-unit.

## 4. Net names and the KiCad -> Verilog map (`nets.csv`)

`nets.csv` has one row per net: net code, exact KiCad name, `verilog_ident`,
`verilog_base`, node count, driver/load counts, power/ground flags, special
characters, single-node flag and a note. The mapping is deterministic:

1. every character outside `[A-Za-z0-9_]` becomes `_`;
2. runs of `_` collapse to one;
3. a result starting with a digit gets the `n_` prefix;
4. an empty result becomes `n_unnamed`;
5. Verilog keywords get the `n_` prefix.

In this netlist **no collisions occur**: all 4510 identifiers are distinct and
match `[A-Za-z_][A-Za-z0-9_$]*`. Examples:

| KiCad net | Verilog |
|---|---|
| `+5V` | `_5V` |
| `+3V3` | `_3V3` |
| `GND` | `GND` |
| `CLK` | `CLK` |
| `/B01_S01_Supervisor/ACCEPT_A` | `_B01_S01_Supervisor_ACCEPT_A` |
| `unconnected-(U1011A-~{Q}-Pad6)` | `unconnected_U1011A_Q_Pad6_` |
| `unconnected-(U5013-Oa<b-Pad7)` | `unconnected_U5013_Oa_b_Pad7_` |

The rule is collision-safe only because the netlist happens to be so; the script
detects collisions and would suffix `_c<netcode>` deterministically (the column
`note` would say `collision(...)`) - none were needed. Note the rails become
`_5V` / `_3V3` (legal but ugly); a readable alias layer (`VDD5`, `VDD3`, `GND`)
may be added later without changing the map.

## 5. Netlist quirks

### 5.1 Nets with a single node - 667

* 641 are `unconnected-(<ref>-<pin>-Pad<N>)` nets. All 641 carry an explicit
  no-connect flag in the schematic (`pintype` has the `+no_connect` suffix, or
  the pin itself is `no_connect` as on 6264 pin 1), i.e. the designer marked
  them deliberately - they are not accidentially floating pins.
  Distribution by part: Conn_02x20 145, 74HC283 110, 74HC161 95, 74HC138 54,
  74HC74 45, 74HCT574 38, 74HC157 38, 74HCT273 32, 74HCT541 17, 74LS148 12,
  74HC04 10, 74HC32 8, HY6264AxP 7, 74HC08 7, 74HC85 6, 74HC02 6, 74HC238 5,
  Conn_02x12 3, 27C512 3.
* 26 are real named nets with exactly one pin - dangling hierarchical labels or
  outputs. They must not become top-level ports; they are dead unless the model
  drives them:

| net | pin | note |
|---|---|---|
| /B01_S01_Supervisor/MCR0..MCR4 | U1004 (74HCT574) Q | register outputs, unused |
| /B01_S01_Supervisor/MCR15 | U1005 (74HCT574) | unused |
| /B01_S01_Supervisor/NOT_RESET_N | U1016 (74HC04) | unused inverter output |
| /B02_S02_Timing/CAPTURE_N, DONE_ST_N, HOLD_N, RELEASE_N, WAIT_N | U2004 (74HC138) | 5 of 8 decoder outputs unused |
| /B02_S02_Timing/MC_REG0..MC_REG2 | U2003 (74HCT574) | unused |
| /B02_S02_Timing/READ_I | U2011 (74HC04) | unused |
| /B05_S05_Pool1/IDLE_OR, /B07_S05_Pool2/IDLE_OR | U5031 / U5131 (74HC32) | unused gate outputs |
| ARGMAX_RESULT_VALID | U6034 (74HC32) | unused |
| FC1_FC2_DONE_NC, FC2_FC1_DONE_NC, POOL1_P2_DONE_NC, POOL2_P1_DONE_NC | 74HC08 | deliberately unused ("NC") |
| POOL1_OUT_WE_NC, POOL2_OUT_WE_NC | 74HCT541 | output enable unused |
| POOL_MEM_nCE_OUT | U12504 (74HC157) | unused mux output |

Note the asymmetry that proves these are labels, not wires: `/B01_S01_Supervisor/MC5..MC15`
are 2-3 node nets, but `MCR5..MCR8` and `MCR12..MCR14` do not exist at all (those
register outputs have explicit no-connects).

### 5.2 Special characters in net names

| char | n nets | where |
|---|---|---|
| `/` | 3330 | every hierarchical net (`/SheetName/LABEL`) |
| `-` | 641 | only inside `unconnected-(...)` |
| `(` `)` | 641 | `unconnected-(...)` |
| `~` `{` `}` | 90 | `unconnected-(...-~{Q}-...)` from 74HC74 `~Q` pins |
| `+` | 2 | `+5V`, `+3V3` |
| `<` | 3 | `unconnected-(U5013-Oa<b-Pad7)` etc. (74HC85 `Oa<b` pin) |
| `=` | 3 | `unconnected-(U5013-Oa=b-Pad6)` etc. |
| `[` `]` | 0 | none |
| space, `#`, `*`, `.`, `:` | 0 | none |

Longest names are 40 chars (`/B01_S01_Supervisor/NOT_RESULT_VALID_SET`,
`.../RESULT_VALID_CLEAR_N`). No duplicate net names.

### 5.3 Unconnected / missing pins

* 641 explicit `unconnected-*` nets (§5.1).
* **25 packages are only partially placed**: a multi-unit symbol is used for one
  gate/FF but the other units were never placed, so their pins do not appear in
  the netlist at all (not even as `unconnected-*`). These must be left floating
  (or tied off) in the Verilog; driving them would create extra loads:

| ref | part | unused units | pins absent |
|---|---|---|---|
| U2010, U14006, U15006, U9132, U9332, U12014 | 74HC08 | B,C,D | 4,5,6,8,9,10,11,12,13 |
| U8142, U9127, U9327 | 74HC00 | B,C,D | 4,5,6,8,9,10,11,12,13 |
| U4056, U4064, U15013 | 74HC32 | B,C,D | 4,5,6,8,9,10,11,12,13 |
| U7143, U14013, U8143, U9117, U9317 | 74HC32 | C,D | 8..13 |
| U2011, U14005, U15005 | 74HC04 | C,D,E,F | 5,6,8..13 |
| U7139 | 74HC04 | F | 12,13 |
| U9130, U9330 | 74HC04 | D,E,F | 8..13 |
| U16022, U16222 | 74HC74 | B | 8..13 |

### 5.4 Power pins and rails

* Three rails exist: `GND` (3428 nodes), `+5V` (1568), `+3V3` (129).
* 897 `power_in` pins, all correctly connected: every `VCC` pin on `+5V`, every
  `GND` pin on `GND`. **No power pin is missing, floating or on the wrong rail**
  (`stats.json:power_pin_anomalies` is empty).
* **`+3V3` has no on-board consumer**: it appears only on the backplane
  connectors (128 pins) and the `PWR_FLAG`. It is an incoming rail only, so it
  can be a top-level port that nothing drives inside the design.
* The rails double as logic constants: 2277 signal pins are strapped to `GND` or
  `+5V` (74HC157 552, 74HC283 500, 74HC688 413, 74HC161 263, 27C512 146,
  74HCT574 103, 74HCT541 80, ...). Examples: 74HC157 `E` tied low (enable),
  74HC283 `B*` inputs tied low for unused operand bits, 74HC161 `D0..D3` tied
  low, 74HC688 `P*` tied high. A Verilog model must treat `_5V`/`GND` as
  constant 1/0 rather than as undriven wires.
* KiCad marks all nets class "Default"; there is no separate power class.

### 5.5 The clock is driven through a 33 ohm resistor

`CLK` (199 nodes: 184 clock inputs, 11 backplane connector pins, test points)
has **no logic driver**. The chain is
`X10001.3 -> OSC_OUT -> JP10001.1|2 -> CLK_SEL -> U10001.11 (74HC04) -> pin 10 ->
CLK_BUF -> R10005 (33R) -> CLK`. If resistors are simply dropped, `CLK` becomes
undriven. Either model `R10005` as a wire (recommended) or short `CLK_BUF` to
`CLK` and keep the inverter as the clock buffer.

### 5.6 Nets with no logic driver - 46

Besides `CLK` (above) these are the external/pull-up interfaces:

* `H_A0..H_A23`, `H_LOAD_nOE`, `H_LOAD_nWE`, `H_MEM_SEL0..H_MEM_SEL4` - header
  side of the backplane interface, pulled up by `RN10001..RN10003` (address) and
  `R10007`/`R10008` (load strobes), `R10011..R10015` (MEM_SEL); driven from
  off-board (they also enter 74HCT245 A-side pins, which the symbol types as
  inputs).
* `LOAD_EN`, `IMAGE_DONE_N`, `MODEL_DONE_N` - pulled up, driven from the
  backplane.
* `/B12_S10_Top_IO/CLK_SEL`, `/B12_S10_Top_IO/EXT_CLK_IN` - 3-pin clock-select
  jumper `JP10001` plus 10k pull resistors (open = on-board oscillator).
* `/B12_S10_Top_IO/RESET_RAW`, `/B12_S10_Top_IO/START_RAW` - push button / RC /
  header.
* `/B12_S10_Top_IO/LED_*` - LED anode nets; each is the far side of a series
  resistor whose near side is the matching `/B12_S10_Top_IO/ST_*` net (e.g.
  `ST_BUSY - R10017 - LED_BUSY - D10002`). Shorting the resistors merges
  `LED_*` into `ST_*`.

These 46 nets are the natural top-level input ports of the Verilog, except the
seven `LED_*` nets, which are internal nodes once the series resistors are
short-circuited.

### 5.7 Bus contention / tri-state

85 nets have more than one driver. The widest are the memory data buses
`/B03_S04_Memories/MEM_D0..MEM_D7` with 29 tri-state drivers each (12 28C256 +
8 27C512 + 7 HY6264AxP + 2 74HC245). `ADDR0..` have 10 drivers each (74HCT541
banks). These must be modelled as `wire` with tri-state (`1'bz`) drivers, not as
`reg`-driven nets.

### 5.8 Library / netlist discrepancies

Six parts used by the schematic are **absent from the installed
`74xx.kicad_sym`** (KiCad 10.0.4). They are pin-compatible aliases declared by
the project generator (`tools/kicad_gen.py:default_registry`):

| part used | symbol it was drawn from | result of pin-by-pin comparison |
|---|---|---|
| 74HC157 | 74LS157 | identical names/types/units |
| 74HC161 | 74LS161 | identical |
| 74HC283 | 74LS283 | identical |
| 74HC08 | 74LS08 | identical |
| 74HC32 | 74LS32 | identical |
| 74HCT245 | 74LS245 | identical |

`74HCT541`, `74HCT574`, `74HCT273`, `74HC688`, `74HC85`, `74HC245`, `74HC04`,
`74HC02` are `extends`-derived symbols and were flattened through the
`extends` chain before comparison.

Two symbol-level oddities worth knowing:

* `HY6264AxP` keeps `VCC`/`GND` in the **common body (unit 0)**; the netlist
  instantiates all 28 pins in unit `A`. `pins.json` reports `unit=1` /
  `lib_unit=0` for those two pins - expected, not an error.
* `HY6264AxP` pin 1 is `NC` (`no_connect`) and is correctly attached to a dummy
  `unconnected-(U40xx-NC-Pad1)` net on all seven devices.

### 5.9 Floating data bits on the bus-map ROM

`U12005` (27C512, `B11_S11_BusFabric`) has `D5`, `D6`, `D7` unconnected; only
`MAP_SEL0..MAP_SEL4` are wired. The model must return 0 (or X) on the unused
upper three bits; `bus_map.bin` only uses the low 5 bits.

### 5.10 Nets that exist only on mechanical parts - 157

Excluding `unconnected-*`, only a handful: `+3V3`, `/B12_S10_Top_IO/EXT_CLK_IN`,
`/B12_S10_Top_IO/OSC_OUT` (oscillator -> jumper) and the seven
`/B12_S10_Top_IO/LED_*` nets. The rest (147) are unused connector pins.

## 6. Parts whose pin names are ambiguous or missing

| part | issue |
|---|---|
| 74HC00, 74HC02, 74HC04, 74HC08, 74HC32 | gate inputs/outputs have **empty names** (12 unnamed pins per package; 74HC04: 6 outputs). Only the unit letter + pin number identify the role. Role must come from the pin number (e.g. 74HC00 unit A = 1,2 in / 3 out). |
| 74LS148 | pin 10 is named **`IO`** (capital letter O) but is `I0` (input 0, zero). All 14 signal pins are drawn active-low (inverted graphic) but none carries `~{}` in the name. Outputs are named `S0/S1/S2` (datasheet: A0/A1/A2), `GS`, `EO`. |
| 74HC245 / 74HCT245 | pin 1 is named **`A->B`** (contains `->`, not identifier-safe); pin 19 is `CE` but is active-low (`~OE`), polarity only via the inverted graphic. A/B pins are typed `tri_state`, DIR/OE `input`. |
| 74HCT574 | pin 1 `OE` is active-low (inverted graphic, no overbar in the name); pin 11 is `Cp` (clock). |
| 74HCT273 | pin 1 `~{Mr}` (master reset, mixed case), pin 11 `Cp`. |
| 74HC688 | pin 1 `G` is active-low (inverted graphic); pin 19 is named **`P=R`** (contains `=`). Pins `P0..P7` / `R0..R7`. |
| 74HC85 | pins named **`Ia<b`, `Ia=b`, `Ia>b`, `Oa<b`, `Oa=b`, `Oa>b`** - contain `<` and `=`. |
| 74HC138 | `~{E0}`, `~{E1}` (active-low enables) and `E2` (active-high enable) - easy to mix up; `~{Y0}..~{Y7}` outputs. |
| 74HC238 | `~{E1}`, `~{E2}`, `E3`, `Y0..Y7` (no overbars on outputs). |
| 74HC161 | `~{MR}`, `~{PE}`, `CEP`, `CET`, `TC` (TC is active-high). |
| 74HC157 | pin 1 `S` and pin 15 `E` are shared by the four muxes; the muxes are distinguished only by suffix `a/b/c/d` on `I0x/I1x/Zx`. Unambiguous, but note `E` is active-low (inverted graphic). |
| 74HC74 | pin names `~{R}`, `~{S}`, `D`, `C`, `Q`, `~{Q}` repeat in units A and B (only unique per unit). Power unit is `C` (pins 7/14). |
| 27C512 / 28C256 | control pins `~{CE}` / `~{CS}`, `~{OE}`, `~{WE}` - all active-low, overbar notation is present. |
| HY6264AxP | `~{CS1}`, `CS2`, `~{OE}`, `~{WE}`, `I/O0..I/O7`, `NC` (pin 1). |

**Polarity warning.** The netlist carries only pin *name* and *type*. Several
active-low pins are expressed **only** by the inverted pin graphic and have a
plain name: 74HCT574 `OE` (p1), 74HC245/74HCT245 `CE` (p19), 74HC157 `E` (p15),
74HCT541 `G1`/`G2` (p1/p19), 74HC688 `G` (p1) and `P=R` (p19), 74HC00/02/04
outputs. These are listed per part in `pins.json:active_low_by_graphic_only`.
A Verilog model must invert them; taking the name at face value will produce
wrong behaviour.

## 7. Parts to skip for logic simulation, and the nets they touch

These 431 packages carry no logic. They must be removed from the netlist before
Verilog generation; the nets listed are the ones they touch (full detail in
`stats.json:skipped` and `nets.csv`).

| part | n | why skipped | nets touched |
|---|---|---|---|
| C | 268 | decoupling capacitors | `GND` (268), `+5V` (267); **one exception**: `C10011` sits on `/B12_S10_Top_IO/RESET_RAW` (reset RC delay) |
| R | 32 | resistors (pull-ups, LED series, 33R clock series) | `+5V` (15), `GND` (10), `LOAD_EN`, `IMAGE_DONE_N`, `MODEL_DONE_N`, `MEM_SEL0..4`, `LOAD_nWE`, `LOAD_nOE`, `/B12.../RESET_RAW`, `START_RAW`, `CLK_SEL`, `EXT_CLK_IN`, `CLK_BUF`, `CLK`, `H_LOAD_nWE`, `H_LOAD_nOE`, `H_MEM_SEL0..4`, `LED_PWR`, `LED_BUSY`, `ST_BUSY`, `LED_DONE`, `ST_DONE`, `LED_RESULT_VALID`, `ST_RESULT_VALID`, `LED_ERROR`, `ST_ERROR`, `LED_IMAGE_READY`, `ST_IMAGE_READY`, `LED_MODEL_READY`, `ST_MODEL_READY` (38 nets) |
| R_Network08 | 3 | 8-resistor SIP networks (pull-ups) | `GND` + `H_A0..H_A23` (25 nets) |
| LED | 7 | indicator LEDs | `GND` + `LED_PWR`, `LED_BUSY`, `LED_DONE`, `LED_RESULT_VALID`, `LED_ERROR`, `LED_IMAGE_READY`, `LED_MODEL_READY` (8 nets) |
| TestPoint | 77 | probe pads | 66 nets, all of them also reaching a logic pin (pure observation); e.g. `CLK`, `RESET_N`, `START`, `BUSY`, `DONE`, `ERROR`, `RESULT_VALID`, `MEM_ACK`, `MEM_DONE`, `MEM_BUSY`, `REQ`, `WE`, `MEM_nCE`, `MEM_nOE`, `MEM_nWE`, `C1_*`/`C2_*`/`FC*` status signals. Top-level observation ports are a natural replacement. |
| PWR_FLAG | 3 | ERC-only symbols | `+5V`, `+3V3`, `GND` |
| Conn_02x20_Odd_Even | 33 | 2x20 backplane headers | 460 nets: the whole backplane bus (`CLK`, `ADDR0..23`, `DATA*`, `MEM_*`, `H_*`, `LED_*`, ...). 145 of these connector pins are unconnected. |
| Conn_02x16_Odd_Even | 1 | 2x16 header | 28 nets (`H_A*`, `H_LOAD_*`, `IMAGE_DONE_N`, `LOAD_EN`, ...) |
| Conn_02x12_Odd_Even | 1 | 2x12 header | 20 nets (`LOAD_*`, `MEM_SEL*`, `IMAGE_DONE_N`, `MODEL_DONE_N`, ...) |
| Conn_02x10_Odd_Even | 1 | 2x10 header | 16 nets |
| Conn_02x02_Odd_Even | 1 | 2x2 header | 2 nets |
| Conn_01x02 | 3 | 2-pin headers (start/reset/external clock) | `RESET_RAW`, `START_RAW`, `EXT_CLK_IN`, `GND` |
| Conn_01x03 | 1 | 3-pin clock-select jumper `JP10001` | `OSC_OUT`, `CLK_SEL`, `EXT_CLK_IN` |

Kept but modelled simply (not logic gates): `SW_Push` (1, reset button on
`RESET_RAW`/`GND`) and `ASE-xxxMHz` (1, 8.000 MHz oscillator: pin 1 `EN` on
`+5V`, pin 2 `GND` on `GND`, pin 3 `OUT` -> `OSC_OUT`, pin 4 `Vdd` on `+5V`).
Mounting holes: **none in this netlist** (no `MountingHole` symbol is used).

## 8. Memories (`memories.csv`)

71 devices. Groups and the most likely `model/` image (address/data/control pin
lists with net names are in the CSV):

| sheet | devices | init image |
|---|---|---|
| B01_S01_Supervisor | 2x 27C512 (U1001, U1002) | `microcode/supervisor_lo.bin` (MC0..MC7 -> D0..D7), `supervisor_hi.bin` (MC8..MC15) - **high confidence**: CE/OE tied low, address = ST0..ST4 + START_S + IMG_RDY_S + MDL_RDY_S + the seven *_DONE flags + TIMEOUT_I (16 bits), exactly the 64K supervisor word format of `tools/gen_supervisor_microcode.py` |
| B02_S02_Timing | 1x 27C512 (U2001) | **unknown** - only 6 address bits are signal-driven (TS0..TS2 on A0..A2, then REQ_S / WAIT_MATCH / WE_S; the rest are tied low), and no `timing`/`s02` image exists in `model/microcode` |
| B03_S04_Memories | 7x HY6264AxP (U4001..U4007) | none (volatile SRAM; feature maps INPUT/C1OUT/P1OUT/C2OUT/P2OUT/FC1OUT/FC2LOG) |
| B03_S04_Memories | 12x 28C256 (U4008..U4019) | **unknown** - weights (W_CONV1/2, W_FC1/2), bias (B_*) and qparam (Q_*) nibbles are loaded at runtime; no image in `model/` |
| B03_S04_Memories | 8x 27C512 (U4020..U4027) | `lut/lut_lo.bin` / `lut/lut_hi.bin` per pair 0..3 (CE net `nCS_LUT<n>_LO/_HI`) - high confidence |
| B04_S07_Conv1 | 8x 27C512 (U7077..U7084) | `lut/lut_lo.bin` / `lut_hi.bin` (data bus `C1_P1..P4_0..15`) |
| B04_S07_Conv1 | 2x 27C512 (U7132, U7133) | `microcode/c1_rom1.bin`, `c1_rom2.bin` (data bus `C1_MC1_*` / `C1_MC2_*`), 11 address bits |
| B06_S08_Conv2 | 8x 27C512 (U8078..U8085) | `lut/lut_lo.bin` / `lut_hi.bin` |
| B06_S08_Conv2 | 2x 27C512 (U8132, U8133) | `microcode/c2_rom1.bin`, `c2_rom2.bin` |
| B08_S09_FC1 | 8x 27C512 (U9063..U9070) | `lut/lut_lo.bin` / `lut_hi.bin` |
| B08_S09_FC1 | 2x 27C512 (U9118, U9119) | `microcode/fc_rom1.bin`, `fc_rom2.bin` - **medium confidence** |
| B09_S09_FC2 | 8x 27C512 (U9263..U9270) | `lut/lut_lo.bin` / `lut_hi.bin` |
| B09_S09_FC2 | 2x 27C512 (U9318, U9319) | `microcode/fc_rom1.bin`, `fc_rom2.bin` - **medium confidence** |
| B11_S11_BusFabric | 1x 27C512 (U12005) | `busmap/bus_map.bin` (data = MAP_SEL0..4; D5..D7 floating) |

Why FC is "medium": `model/microcode` contains only one `fc_rom1/fc_rom2` pair
while the netlist has two FC sheets, each with its own `FC_MC1`/`FC_MC2` ROM.
Either both halves run the same microcode (most likely, FC1/FC2 are two
identical 64-input halves) or one of the two sheets should use a different
image that does not exist. This must be confirmed before trusting FC
simulation.

`model/requant/*.bin` (c1/c2/fc requant hi/lo, 2 KB each) have **no
corresponding device in this netlist** - the requant blocks (S13/S15) are built
from 74HC283/74HC157/74HC273/74HC85 logic, not ROMs. They are listed in
`stats.json:model_files_unused`.

Every 27C512/28C256/6264 has all 8 data pins on `MEM_D0..7` (or its own bus) and
its address pins on `MADDR*`; the `addr_pins_used` column counts address pins
that are actually signal-driven (the rest are tied low/high), e.g. 16 for LUT
ROMs, 11 for microcode ROMs, 6 for the timing ROM, 8 for the bus-map ROM.

## 9. Verification performed

* Netlist parsed with the project's own `tools/kicad_sexpr.py`; component count,
  node count and every pin reference cross-checked (1329 components, 17654
  nodes, no node references a missing component and no component is missing
  from the nets).
* Every part's pin set compared to the KiCad symbol (after `extends`/alias
  resolution): 0 name mismatches, 0 type mismatches, 0 unit conflicts.
* Pin counts vs. footprint-derived package size: all DIP parts OK.
* All 4510 sanitised net identifiers validated against
  `[A-Za-z_][A-Za-z0-9_$]*`, all distinct.
* Memory control/address/data pins were resolved through the symbol pin names,
  not by pin-number guessing, and the resulting nets were matched against the
  sheet names and the generator scripts (`tools/build_memories.py`,
  `build_supervisor.py`, `build_conv1.py`, `build_fc.py`, `build_bus.py`,
  `gen_supervisor_microcode.py`).

## 10. Files

| file | contents |
|---|---|
| `parts.csv` | 24 modelled parts: count, lib, category, model kind, package, pin check, sheets, notes |
| `pins.json` | pin number -> name/type/unit for every modelled part, incl. power pins, pin graphics and active-low flags |
| `nets.csv` | all 4510 nets: code, KiCad name, Verilog identifier, node/driver/load counts, power/ground flags, special chars, notes |
| `memories.csv` | all 71 memory devices with address/data/control pins and the proposed init image |
| `stats.json` | machine-readable statistics behind this report |
| `build_analysis.py` | regenerates all of the above from `top.net` (read-only) |
| `validate.py` | re-checks the artefacts against the netlist (320 assertions) |

Regenerate and verify with:

```
python -I build_analysis.py
python -I validate.py
```
