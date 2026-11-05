"""Generate the 64K x 16 supervisor microcode ROM images and a summary table."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(PROJECT_DIR, "model", "microcode")
os.makedirs(OUT, exist_ok=True)

G_RESET, G_WAIT_READY, G_IDLE = 0, 1, 2
STARTS = [3, 5, 7, 9, 11, 13, 15]
WAITS = [4, 6, 8, 10, 12, 14, 16]
G_FINISH, G_WAIT_START_LOW, G_ERROR = 17, 18, 19
STAGE = {3: 1, 5: 2, 7: 3, 9: 4, 11: 5, 13: 6, 15: 7}


def microcode(state: int, start: int, img: int, mdl: int,
              done: tuple[int, ...], to: int) -> int:
    c1, p1, c2, p2, fc1, fc2, am = done
    ready = img & mdl
    ns = state
    busy = 1 if 3 <= state <= 16 else 0
    done_bit = 0
    rv = 0
    err = 0
    stage = 0
    tclr = 0
    # Phase selects are held through the matching WAIT state so the pool and
    # FC engines keep the same phase for the whole stage.
    pool_sel = 1 if state in (9, 10) else 0      # P2 (POOL2)
    fc_sel = 1 if state in (13, 14) else 0       # FC2

    if state == G_RESET:
        ns = G_WAIT_READY
    elif state == G_WAIT_READY:
        if start and not ready:
            ns = G_ERROR
        elif ready:
            ns = G_IDLE
        else:
            ns = G_WAIT_READY
    elif state == G_IDLE:
        if start:
            ns = 3 if ready else G_ERROR
        else:
            ns = G_IDLE
    elif state in STARTS:
        ns = state + 1
        stage = STAGE[state]
        tclr = 1
    elif state in WAITS:
        k = WAITS.index(state)
        if to:
            ns = G_ERROR
        elif done[k]:
            ns = state + 1
        else:
            ns = state
    elif state == G_FINISH:
        ns = G_WAIT_START_LOW
        done_bit = 1
        rv = 1
    elif state == G_WAIT_START_LOW:
        ns = G_IDLE if not start else G_WAIT_START_LOW
    elif state == G_ERROR:
        ns = G_ERROR
        err = 1

    if state == G_ERROR:
        err = 1

    word = (ns & 0x1F) | (busy << 5) | (done_bit << 6) | (rv << 7) | (err << 8)
    word |= (stage & 0x7) << 9
    word |= (tclr & 1) << 12
    word |= (pool_sel & 1) << 13
    word |= (fc_sel & 1) << 14
    return word


lo = bytearray(65536)
hi = bytearray(65536)
for addr in range(65536):
    state = addr & 0x1F
    start = (addr >> 5) & 1
    img = (addr >> 6) & 1
    mdl = (addr >> 7) & 1
    done = tuple((addr >> (8 + i)) & 1 for i in range(7))
    to = (addr >> 15) & 1
    if state > 19:
        word = 0
    else:
        word = microcode(state, start, img, mdl, done, to)
    lo[addr] = word & 0xFF
    hi[addr] = (word >> 8) & 0xFF

with open(os.path.join(OUT, "supervisor_lo.bin"), "wb") as f:
    f.write(lo)
with open(os.path.join(OUT, "supervisor_hi.bin"), "wb") as f:
    f.write(hi)
with open(os.path.join(OUT, "supervisor_lo.hex"), "w", encoding="ascii", newline="\n") as f:
    f.writelines(f"{b:02X}\n" for b in lo)
with open(os.path.join(OUT, "supervisor_hi.hex"), "w", encoding="ascii", newline="\n") as f:
    f.writelines(f"{b:02X}\n" for b in hi)

# A compact table for the interesting condition cases.
rows = []
for state in range(20):
    for start in (0, 1):
        for ready in (0, 1):
            for to in (0, 1):
                for done_mode in ("none", "own"):
                    done = [0] * 7
                    if done_mode == "own" and state in WAITS:
                        done[WAITS.index(state)] = 1
                    w = microcode(state, start, ready, ready, tuple(done), to)
                    rows.append((state, start, ready, to, done_mode, w & 0x1F,
                                 (w >> 5) & 1, (w >> 6) & 1, (w >> 7) & 1,
                                 (w >> 8) & 1, (w >> 9) & 7, (w >> 12) & 1,
                                 (w >> 13) & 1, (w >> 14) & 1))
with open(os.path.join(OUT, "supervisor_table.csv"), "w", encoding="utf-8", newline="\n") as f:
    f.write("state,start,ready,timeout,done_mode,next,busy,done,result_valid,error,stage_code,timeout_clr,pool_sel,fc_sel\n")
    for r in rows:
        f.write(",".join(str(x) for x in r) + "\n")

print("wrote supervisor_lo/hi.bin and .hex (65536 bytes each)")
print("checksum lo", sum(lo) & 0xFFFFFFFF, "hi", sum(hi) & 0xFFFFFFFF)
# Known-address spot checks
def check(addr, expect_state, expect_busy):
    w = lo[addr] | (hi[addr] << 8)
    ns = w & 0x1F
    busy = (w >> 5) & 1
    print(f"addr 0x{addr:04X}: next={ns} busy={busy} done={(w>>6)&1} rv={(w>>7)&1} err={(w>>8)&1} stage={(w>>9)&7} tclr={(w>>12)&1}")
    assert ns == expect_state and busy == expect_busy

# state 0, no conditions -> 1
check(0, 1, 0)
# state 1, img=mdl=1 -> 2; address bits A6/A7=1
check(1 | (1 << 6) | (1 << 7), 2, 0)
# state 2, start=1, ready=1 -> 3
check(2 | (1 << 5) | (1 << 6) | (1 << 7), 3, 0)
# state 3 (C1_START) -> 4, busy=1
check(3, 4, 1)
# state 4 (C1_WAIT), c1 done=1 -> 5
check(4 | (1 << 8), 5, 1)
print("PASS: supervisor microcode spot checks")
