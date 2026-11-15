"""Byte-compare the same vector's layer dumps across clock frequencies."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def hb(p):
    with open(p, encoding="ascii") as f:
        return [int(x, 16) for x in f if x.strip()]


def main(dirs):
    layers = ["INPUT", "C1OUT", "P1OUT", "C2OUT", "P2OUT", "FC1OUT", "FC2LOG"]
    ref = dirs[0]
    v = 16
    bad = 0
    for lay in layers:
        base = None
        for d in dirs:
            p = os.path.join(HERE, d, "dump_%s_%d.hex" % (lay, v))
            if not os.path.exists(p):
                print("%-7s MISSING %s" % (lay, d))
                bad += 1
                base = None
                break
            a = hb(p)
            if base is None:
                base = (d, a)
            elif a != base[1]:
                n = sum(1 for x, y in zip(a, base[1]) if x != y)
                print("%-7s DIFFER %s vs %s (%d bytes)" % (lay, d, base[0], n))
                bad += 1
        if base:
            print("%-7s identical across %d runs (%d bytes)" % (lay, len(dirs), len(base[1])))
    print("\nFREQUENCY INVARIANCE: %s" % ("PASS" if bad == 0 else "FAIL"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
