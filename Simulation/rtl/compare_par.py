"""Bitwise compare the per-vector dumps from the parallel runs against the
software-model expected files in weights/x28s/vectors/."""
import os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
VEC = os.path.join(ROOT, "weights", "x28s", "vectors")
RTL = os.path.dirname(os.path.abspath(__file__))


def rd(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def cmp_file(dump, exp, le32=False):
    a, b = rd(dump), rd(exp)
    if le32:                       # dump: 40 byte lines; exp: 10 int32 words
        assert len(a) == 40 and len(b) == 10, (len(a), len(b))
        a32 = ["".join(a[i:i + 4][::-1]) for i in range(0, 40, 4)]
        return a32 == b, 10
    return a == b, len(a)


def main():
    ids = [int(x) for x in sys.argv[1:]] or list(range(8))
    total_bad = 0
    for k in ids:
        d = os.path.join(RTL, "sim_v%d" % k)
        res = {}
        for name, dump, le in (("c1", "dump_C1OUT_%d.hex", False),
                               ("p1", "dump_P1OUT_%d.hex", False),
                               ("c2", "dump_C2OUT_%d.hex", False),
                               ("p2", "dump_P2OUT_%d.hex", False),
                               ("fc1", "dump_FC1OUT_%d.hex", False)):
            ok, n = cmp_file(os.path.join(d, dump % k),
                             os.path.join(VEC, "exp_%s_%d.hex" % (name, k)), le)
            res[name] = (ok, n)
        ok, n = cmp_file(os.path.join(d, "dump_FC2LOG_%d.hex" % k),
                         os.path.join(VEC, "logit_%d.hex" % k), True)
        res["fc2"] = (ok, n)
        line = "vec %d " % k + " ".join(
            "%s:%s" % (n2, "OK" if ok else "FAIL") for n2, (ok, _) in res.items())
        print(line)
        total_bad += sum(0 if ok else 1 for ok, _ in res.values())
    print("ALL LAYERS BYTE-EXACT for 8 vectors: %s" % (total_bad == 0))
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
