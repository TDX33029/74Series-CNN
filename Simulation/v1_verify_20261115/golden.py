"""Independent golden reference for the 74CNN-BRD V2 signed-int8 network.

Deliberately written from scratch (im2col matmul instead of per-pixel loops)
so it can serve as an independent check of both the shipped vectors and the
previous conversation's reference implementation.

Contract (weights/x28s/metadata.json):
    ACC = sum_k a_k * int8(w_k)        signed products, signed accumulate
    Q   = clamp(ACC >> S, 0, 255)      zp = 0, no bias
    S   = 9 (conv1), 10 (conv2), 9 (fc1); fc2 kept as raw int32
Layouts: conv1 8x5x5 -> 24x24; pool1 2x2 max -> 12x12; conv2 16x8x3x3 ->
10x10; pool2 2x2 max -> 5x5; fc1 32x400; fc2 10x32.
"""
import argparse
import os
import struct
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
W = os.path.join(ROOT, "weights", "x28s")
VEC = os.path.join(W, "vectors")
MNIST = os.path.join(ROOT, "MNIST")
S = {"conv1": 9, "conv2": 10, "fc1": 9}


def hexbytes(path):
    with open(path, encoding="ascii") as f:
        return np.array([int(x, 16) for x in f if x.strip()], dtype=np.uint8)


def hexwords(path):
    with open(path, encoding="ascii") as f:
        return [int(x, 16) for x in f if x.strip()]


def i8(path, shape):
    # stored as two's-complement bytes -> wrap to signed int8, then widen
    return hexbytes(path).astype(np.int8).astype(np.int32).reshape(shape)


def clamp8(x):
    return np.clip(x, 0, 255).astype(np.int32)


class Ref:
    def __init__(self, wdir=W):
        self.w1 = i8(os.path.join(wdir, "conv1_weight.hex"), (8, 5, 5))
        self.w2 = i8(os.path.join(wdir, "conv2_weight.hex"), (16, 8, 3, 3))
        self.wf1 = i8(os.path.join(wdir, "fc1_weight.hex"), (32, 400))
        self.wf2 = i8(os.path.join(wdir, "fc2_weight.hex"), (10, 32))

    def forward(self, img_u8):
        img = np.asarray(img_u8, dtype=np.int32).reshape(28, 28)
        # conv1 via sliding windows: (24,24,5,5)
        win = sliding_window_view(img, (5, 5))
        c1 = np.einsum("yxij,oij->oyx", win, self.w1, dtype=np.int32)
        c1 = clamp8(c1 >> S["conv1"])
        # pool1 2x2 max
        p1 = c1.reshape(8, 12, 2, 12, 2).max(axis=(2, 4))
        # conv2: windows over p1 per input channel
        win2 = sliding_window_view(p1, (3, 3), axis=(1, 2))  # (8,10,10,3,3)
        c2 = np.einsum("cyxij,ocij->oyx", win2, self.w2, dtype=np.int32)
        c2 = clamp8(c2 >> S["conv2"])
        p2 = c2.reshape(16, 5, 2, 5, 2).max(axis=(2, 4))
        fc1 = clamp8((self.wf1 @ p2.reshape(400).astype(np.int32)) >> S["fc1"])
        logits = self.wf2 @ fc1.astype(np.int32)
        return c1, p1, c2, p2, fc1, logits.astype(np.int32)


def mnist_idx():
    import gzip
    with gzip.open(os.path.join(MNIST, "t10k-images-idx3-ubyte.gz"), "rb") as f:
        data = f.read()
    n = struct.unpack(">i", data[4:8])[0]
    imgs = np.frombuffer(data, dtype=np.uint8, offset=16).reshape(n, 28, 28)
    with gzip.open(os.path.join(MNIST, "t10k-labels-idx1-ubyte.gz"), "rb") as f:
        lab = np.frombuffer(f.read(), dtype=np.uint8, offset=8)
    return imgs, lab


def write_bytes(path, arr):
    np.asarray(arr, dtype=np.uint8).reshape(-1).tofile(path, sep="\n", format="%02x")


def write_logits(path, lg):
    with open(path, "w", encoding="ascii", newline="\n") as f:
        for v in lg:
            f.write("%08x\n" % (int(v) & 0xFFFFFFFF))


def cmd_selftest(args):
    ref = Ref()
    ok_all = True
    for k in args.ids:
        img = hexbytes(os.path.join(VEC, "img_%d.hex" % k))
        c1, p1, c2, p2, f1, lg = ref.forward(img)
        fails = []
        for name, arr in (("c1", c1), ("p1", p1), ("c2", c2), ("p2", p2), ("fc1", f1)):
            exp = hexbytes(os.path.join(VEC, "exp_%s_%d.hex" % (name, k)))
            if not np.array_equal(np.asarray(arr, np.uint8).reshape(-1), exp):
                bad = int((np.asarray(arr, np.uint8).reshape(-1) != exp).sum())
                fails.append("%s(%d bytes)" % (name, bad))
        exp_lg = hexwords(os.path.join(VEC, "logit_%d.hex" % k))
        got_lg = [int(v) & 0xFFFFFFFF for v in lg]
        if exp_lg != got_lg:
            fails.append("logits")
        ok_all &= not fails
        print("vec %2d: %s%s" % (k, "OK" if not fails else "FAIL " + ",".join(fails),
                                 "" if not fails else ""))
    print("SELFTEST %s" % ("PASS (independent model reproduces shipped vectors bit-exact)"
                           if ok_all else "FAIL"))
    return 0 if ok_all else 1


def cmd_make(args):
    ref = Ref()
    imgs, lab = mnist_idx()
    used = set()
    for k in range(16):
        p = os.path.join(VEC, "meta_%d.txt" % k)
        if os.path.exists(p):
            for line in open(p):
                if line.startswith("index") and int(line.split()[1]) >= 0:
                    used.add(int(line.split()[1]))
    first = args.first
    outdir = os.path.join(args.out, "vectors")
    os.makedirs(outdir, exist_ok=True)
    plan = []
    for d in range(10):
        cand = [i for i in range(first, len(lab)) if int(lab[i]) == d and i not in used]
        if not cand:
            raise SystemExit("no free test image for digit %d" % d)
        idx = cand[0]
        used.add(idx)
        plan.append((d, idx))
    print("plan (digit -> mnist test index): %s" % plan)
    rows = []
    for j, (d, idx) in enumerate(plan):
        k = args.start + j
        img = imgs[idx]
        c1, p1, c2, p2, f1, lg = ref.forward(img)
        write_bytes(os.path.join(outdir, "img_%d.hex" % k), img)
        write_bytes(os.path.join(outdir, "exp_c1_%d.hex" % k), c1)
        write_bytes(os.path.join(outdir, "exp_p1_%d.hex" % k), p1)
        write_bytes(os.path.join(outdir, "exp_c2_%d.hex" % k), c2)
        write_bytes(os.path.join(outdir, "exp_p2_%d.hex" % k), p2)
        write_bytes(os.path.join(outdir, "exp_fc1_%d.hex" % k), f1)
        write_logits(os.path.join(outdir, "logit_%d.hex" % k), lg)
        am = int(np.argmax(lg))
        with open(os.path.join(outdir, "meta_%d.txt" % k), "w", encoding="ascii",
                  newline="\n") as f:
            f.write("index %d\nlabel %d\nargmax %d\n" % (idx, d, am))
        rows.append((k, idx, d, am, [int(v) for v in lg]))
        print("vec %2d: digit %d (mnist idx %3d) -> argmax %d  logits %s"
              % (k, d, idx, am, [int(v) for v in lg]))
        if am != d:
            print("  NOTE: golden model itself misclassifies this image")
    import json
    with open(os.path.join(args.out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump({"vectors": [{"vec": r[0], "mnist_index": r[1], "label": r[2],
                                "argmax": r[3]} for r in rows]}, f, indent=2)
    n_ok = sum(1 for r in rows if r[3] == r[2])
    print("\ngolden-model accuracy on the new real images: %d/10" % n_ok)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("selftest")
    st.add_argument("--ids", nargs="+", type=int, default=list(range(16)))
    mk = sub.add_parser("make")
    mk.add_argument("--out", required=True, help="vector-set root (weights copied here)")
    mk.add_argument("--start", type=int, default=16)
    mk.add_argument("--first", type=int, default=100,
                    help="do not use MNIST test indexes below this")
    a = ap.parse_args()
    return cmd_selftest(a) if a.cmd == "selftest" else cmd_make(a)


if __name__ == "__main__":
    sys.exit(main())
