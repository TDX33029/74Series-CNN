"""Generate init/timing.hex for U2001 (S02 timing controller microcode ROM).

The schematic wires U2001 as

    A[5:0] = {WE_S, WAIT_MATCH, REQ_S, TS2, TS1, TS0}
    D[7:0] = {DONE, ACK, nWE, nOE, nCE, next_TS2, next_TS1, next_TS0}

and the state register is 74HCT273 (U2002), the output register is 74HCT574
(U2003).  The original project has no binary image for this ROM (the analysis
marks U2001 as "unknown"), so this script reconstructs the table from the
state names and the timing description printed on S02:

    IDLE -> SETUP -> WAIT(n) -> CAPTURE(read) / HOLD(write) -> RELEASE -> DONE

REQ_S (A3) is the synchronized request level.  The controller is deliberately
level-sensitive: POOL/ARGMAX hold REQ high to request back-to-back transfers.
The engines drop MEM_REQ at MEM_ACK (one transfer state before DONE) so that
REQ_S is already low when the controller returns to IDLE; otherwise the same
request would start a second, spurious transaction.

Outputs are active low for nCE/nOE/nWE.  WAIT uses the 74HC688 comparator
against the wait counter; WAIT_MATCH is the comparator result.

This is a *reconstructed* image, not extracted from a firmware file.  It is
listed in the verification report as such.  Fill the table below if the real
microcode becomes available.
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "init", "timing.hex")

IDLE, SETUP, WAIT, CAPTURE, HOLD, RELEASE, DONE, GAP_WE = range(8)


def entry(ts: int, req: int, match: int, we: int) -> int:
    """Return the 8-bit microcode word for one ROM address."""
    nce = noe = nwe = ack = done = 1
    nxt = ts

    if ts == IDLE:
        nce, noe, nwe, ack, done = 1, 1, 1, 0, 0
        nxt = SETUP if req else IDLE
    elif ts == SETUP:
        nce, noe, nwe, ack, done = 0, 1, 0 if we else 1, 0, 0
        nxt = WAIT
    elif ts == WAIT:
        nce, noe, nwe, ack, done = 0, 1, 0 if we else 1, 0, 0
        if match:
            nxt = HOLD if we else CAPTURE
        else:
            nxt = WAIT
    elif ts == CAPTURE:            # read data valid
        nce, noe, nwe, ack, done = 0, 0, 1, 1, 0
        nxt = RELEASE
    elif ts == HOLD:               # write: latch HERE (nWE rises on entry),
        # one clock before the engine drops REQ/WE on ACK.  The engine's OUT
        # data buffer is enabled by ~(REQ&WE); releasing nWE in RELEASE put
        # the latch edge in the same clock as the buffer turn-off, i.e. data
        # hold time = 0 (this is what made every write store z).
        nce, noe, nwe, ack, done = 0, 1, 1, 1, 0
        nxt = RELEASE
    elif ts == RELEASE:            # nWE rises here, cycle ends
        # V14b: the POOL latches its 2x2 maximum one clock *after* MEM_ACK
        # (CP state entered on ACK, MAX register clocked at the end of CP).
        # Releasing nCE/nOE in the same clock as ACK left the bus floating
        # exactly when the pool sampled it, so the first value of every
        # window was latched as x and MAX stayed x for the rest of the run.
        # Hold a read's data one extra clock; writes keep the old timing
        # (nWE already rose in HOLD).
        if we:
            nce, noe, nwe, ack, done = 1, 1, 1, 0, 0
        else:
            nce, noe, nwe, ack, done = 0, 0, 1, 0, 0
        nxt = DONE
    elif ts == DONE:
        nce, noe, nwe, ack, done = 1, 1, 1, 0, 1
        # V14: after a *write*, do not fall straight back into IDLE while the
        # master still drives WE.  WE_S is a registered copy of
        # any(REQ & WE), so a master that keeps REQ high (POOL holds it for
        # back-to-back transfers) but has already finished its write pulse
        # still presents WE_S=1 for one more clock.  IDLE would then launch a
        # second, spurious write - measured on the pool: 1552 outputs produced
        # 3102 write cycles, 1151 of them landing on the CONV1_OUT page and
        # storing z there.  Inserting a WE-low gap makes the controller behave
        # edge-triggered for writes while leaving reads back-to-back.
        nxt = GAP_WE if we else IDLE
    elif ts == GAP_WE:
        # Wait for the master's qualified WE to fall so that the stale WE_S
        # cannot launch a duplicate write.  FC2 legitimately holds REQ+WE
        # across its four byte writes (a gap would kill the request, the
        # control register lags one state), so the wait must be bounded:
        # WAIT_MATCH (the 74HC688 against WAITV=15 for writes) acts as the
        # timeout - after it the controller goes back to IDLE and the next
        # write of the burst starts normally.
        nce, noe, nwe, ack, done = 1, 1, 1, 0, 0
        nxt = IDLE if (not we or match) else GAP_WE
    else:                          # unused state
        nce, noe, nwe, ack, done = 1, 1, 1, 0, 0
        nxt = IDLE

    word = (done << 7) | (ack << 6) | (nwe << 5) | (noe << 4) | (nce << 3) | nxt
    return word & 0xFF


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    words = []
    for addr in range(64):
        ts = addr & 7
        req = (addr >> 3) & 1
        match = (addr >> 4) & 1
        we = (addr >> 5) & 1
        words.append(entry(ts, req, match, we))
    # The ROM is 64K; only the low 64 bytes are addressed (A15..A6 grounded).
    words += [0] * (65536 - len(words))
    with open(OUT, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(f"{w:02X}" for w in words) + "\n")
    print(f"wrote {OUT}")
    for addr in range(8):
        print(f"  addr {addr:02X} -> {words[addr]:02X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
