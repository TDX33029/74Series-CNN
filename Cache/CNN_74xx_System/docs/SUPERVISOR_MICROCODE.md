# Supervisor Microcode ROM Map

The supervisor is a 20-state Moore/Mealy hybrid built from a 64K x 16 microcode ROM
(U1/U2, two 27C512), a 74HCT273 state register (U3), and two 74HCT574 output banks
(U4/U5). The ROM address is the concatenation of the current state and the condition
inputs; the ROM data is the next state plus the registered control outputs. Because the
outputs are registered, every control signal changes only on a clock edge, and the
combinational path is limited to ROM access plus the state register setup time.

## ROM address map

| Address bit | Net | Meaning |
|---|---|---|
| A0..A4 | `STATE0..STATE4` | Current state code (0..19) |
| A5 | `START` | Request input (synchronous to the 8 MHz clock) |
| A6 | `IMG_VALID` | Input image is loaded and stable |
| A7 | `MODEL_VALID` | Weights, biases and quantization parameters are loaded |
| A8 | `C1_DONE` | Conv1 macro engine finished its output tile |
| A9 | `P1_DONE` | Pool1 finished |
| A10 | `C2_DONE` | Conv2 finished |
| A11 | `P2_DONE` | Pool2 finished |
| A12 | `FC1_DONE` | FC1 finished |
| A13 | `FC2_DONE` | FC2 finished |
| A14 | `AM_DONE` | Argmax finished, result in `RESULT0..3` |
| A15 | `TIMEOUT` | 24-bit watchdog expired |

Only the low 20 state codes are valid. Addresses with `STATE > 19` are programmed to
`0x0000` (next state 0), so an illegal state returns to reset on the next clock and
raises no control output.

## ROM data map

| Data bit | Net | Meaning |
|---|---|---|
| D0..D4 | `NEXT_STATE0..4` | Next state code |
| D5 | `BUSY` | Registered busy flag (states 3..16) |
| D6 | `DONE` | Registered done pulse (state 17) |
| D7 | `RESULT_VALID` | Registered result-valid pulse (state 17) |
| D8 | `ERROR` | Registered error flag (state 19) |
| D9..D11 | `STAGE_CODE0..2` | Stage decoder input (1=Conv1, 2=Pool1, ... 7=Argmax) |
| D12 | `TIMEOUT_CLR` | Clear the 24-bit watchdog counter (start states) |
| D13..D15 | 0 | Spare |

The 74HC238 decodes `STAGE_CODE` into the seven active-low engine-start strobes.
`BUSY` and `DONE` are exposed to the host through U8/U9; `RESULT_VALID` loads the result
latch U10.

## State table

| Code | State | Entry condition | Exit condition | Control output |
|---|---|---|---|---|
| 0 | `G_RESET` | asynchronous reset | one clock | none |
| 1 | `G_WAIT_READY` | after reset | `IMG_VALID & MODEL_VALID` | none |
| 2 | `G_IDLE` | ready | `START` | none |
| 3 | `G_C1_START` | `START & ready` | one clock | `STAGE=1`, clear watchdog, `BUSY` |
| 4 | `G_C1_WAIT` | after C1 start | `C1_DONE` or `TIMEOUT` | `BUSY` |
| 5 | `G_P1_START` | C1 done | one clock | `STAGE=2`, clear watchdog |
| 6 | `G_P1_WAIT` | after P1 start | `P1_DONE` or `TIMEOUT` | `BUSY` |
| 7 | `G_C2_START` | P1 done | one clock | `STAGE=3` |
| 8 | `G_C2_WAIT` | after C2 start | `C2_DONE` or `TIMEOUT` | `BUSY` |
| 9 | `G_P2_START` | C2 done | one clock | `STAGE=4` |
| 10 | `G_P2_WAIT` | after P2 start | `P2_DONE` or `TIMEOUT` | `BUSY` |
| 11 | `G_FC1_START` | P2 done | one clock | `STAGE=5` |
| 12 | `G_FC1_WAIT` | after FC1 start | `FC1_DONE` or `TIMEOUT` | `BUSY` |
| 13 | `G_FC2_START` | FC1 done | one clock | `STAGE=6` |
| 14 | `G_FC2_WAIT` | after FC2 start | `FC2_DONE` or `TIMEOUT` | `BUSY` |
| 15 | `G_AM_START` | FC2 done | one clock | `STAGE=7` |
| 16 | `G_AM_WAIT` | after Argmax start | `AM_DONE` or `TIMEOUT` | `BUSY` |
| 17 | `G_FINISH` | Argmax done | one clock | `DONE`, `RESULT_VALID` |
| 18 | `G_WAIT_START_LOW` | after finish | `!START` | none |
| 19 | `G_ERROR` | timeout or invalid start | reset only | `ERROR` |

Timing: each state is one 8 MHz clock (125 ns). A start state asserts its `STAGE` strobe
for exactly one clock; the addressed engine latches it and asserts its `*_DONE` when the
final output beat of the stage is written. The supervisor does not inspect addresses or
data; it only sequences the seven engines with a `BUSY`/`DONE` handshake. The watchdog is
cleared in every start state, so each stage gets a fresh 2^24-clock window (2.097 s at
8 MHz); `TIMEOUT` therefore indicates a hung engine, not slow compute.

## Branch cases

`supervisor_table.csv` lists every state with `START`, `ready`, `TIMEOUT` and "own done"
variants. The generated ROM images `supervisor_lo.bin` and `supervisor_hi.bin` are the
byte-exact 27C512 contents. Reproduce them with:

```
python tools/gen_supervisor_microcode.py
```

Expected output ends with `PASS: supervisor microcode spot checks`.

## Why the ROM is registered

A purely combinational next-state decoder would produce a long path through the ROM,
the decoder and the engine handshake. Registering `BUSY`, `DONE`, `RESULT_VALID` and
`ERROR` in U4/U5 guarantees that all handshake outputs are glitch-free and that the
external engines see exactly one-clock-wide strobes. The cost is one extra clock of
latency per transition, which is negligible at 8 MHz relative to a stage that takes
thousands of clocks.
