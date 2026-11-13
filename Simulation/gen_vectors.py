"""Numpy reference model of the V2 signed-int8 CNN (scheme C hardware
contract) and extra-vector generator.

The model reads ONLY the same hex files the boards are programmed with
(weights/x28s/*.hex), applies the V2 quantisation contract
    ACC = sum a_k * int8(w_k)          (signed products, signed accumulate)
    Q    = clamp(ACC >> S, 0, 255)     (zero point 0, no bias; S = 9/10/9)
    FC2  = raw signed int32 accumulator, little-endian bytes in SRAM
and must reproduce the existing expected files bit-exact before it is
allowed to emit new vectors.

Usage:
    python gen_vectors.py --check          # validate against vectors 0..7
    python gen_vectors.py --make 8 9 ...   # emit img/exp/logit for new ids
"""
from __future__ import annotations

import argparse
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "..", "weights", "x28s")
VEC = os.path.join(W, "vectors")


def rdb(path) -> np.ndarray:
    return np.array([int(x, 16) for x in open(path) if x.strip()], dtype=np.uint8)


def loads(path) -> np.ndarray:
    return np.array([int(x, 16) for x in open(path) if x.strip()], dtype=np.uint8)


def int8s(u: np.ndarray) -> np.ndarray:
    return u.astype(np.int8)


def model(img: np.ndarray):
    # ---- conv1: 8 oc, 5x5 valid on 28x28 -> 24x24, S=9
    w1 = int8s(loads(os.path.join(W, "conv1_weight.hex"))).reshape(8, 5, 5)
    img = img.astype(np.int32).reshape(28, 28)
    c1 = np.zeros((8, 24, 24), dtype=np.int32)
    for oc in range(8):
        for y in range(24):
            for x in range(24):
                acc = int(np.sum(img[y:y+5, x:x+5] * w1[oc]))
                c1[oc, y, x] = min(max(acc >> 9, 0), 255)
    # ---- pool1: 2x2 max -> 12x12
    p1 = c1.reshape(8, 12, 2, 12, 2).max(axis=(2, 4))
    # ---- conv2: 16 oc x 8 ic, 3x3 valid on 12x12 -> 10x10, S=10
    w2 = int8s(loads(os.path.join(W, "conv2_weight.hex"))).reshape(16, 8, 3, 3)
    c2 = np.zeros((16, 10, 10), dtype=np.int32)
    for oc in range(16):
        for y in range(10):
            for x in range(10):
                acc = 0
                for ic in range(8):
                    acc += int(np.sum(p1[ic, y:y+3, x:x+3] * w2[oc, ic]))
                c2[oc, y, x] = min(max(acc >> 10, 0), 255)
    # ---- pool2: 2x2 max -> 5x5 (flat 400)
    p2 = c2.reshape(16, 5, 2, 5, 2).max(axis=(2, 4))
    # ---- fc1: 32 neurons x 400, S=9
    wf = int8s(loads(os.path.join(W, "fc1_weight.hex"))).reshape(32, 400)
    pv = p2.reshape(400).astype(np.int32)
    fc1 = np.zeros(32, dtype=np.int32)
    for n in range(32):
        acc = int(np.sum(pv * wf[n]))
        fc1[n] = min(max(acc >> 9, 0), 255)
    # ---- fc2: 10 logits x 32, raw int32
    w2f = int8s(loads(os.path.join(W, "fc2_weight.hex"))).reshape(10, 32)
    logits = np.zeros(10, dtype=np.int32)
    for l in range(10):
        logits[l] = int(np.sum(fc1.astype(np.int32) * w2f[l]))
    return c1, p1, c2, p2, fc1, logits


def write_bytes(path, arr):
    with open(path, "w", encoding="ascii", newline="\n") as f:
        for b in np.asarray(arr, dtype=np.uint8).reshape(-1):
            f.write("%02x\n" % b)


def write_vec(k, img, label=-1):
    c1, p1, c2, p2, fc1, lg = model(img)
    write_bytes(os.path.join(VEC, "img_%d.hex" % k), img)
    write_bytes(os.path.join(VEC, "exp_c1_%d.hex" % k), c1)
    write_bytes(os.path.join(VEC, "exp_p1_%d.hex" % k), p1)
    write_bytes(os.path.join(VEC, "exp_c2_%d.hex" % k), c2)
    write_bytes(os.path.join(VEC, "exp_p2_%d.hex" % k), p2)
    write_bytes(os.path.join(VEC, "exp_fc1_%d.hex" % k), fc1)
    with open(os.path.join(VEC, "logit_%d.hex" % k), "w",
              encoding="ascii", newline="\n") as f:
        for v in lg:
            f.write("%08x\n" % (int(v) & 0xFFFFFFFF))
    am = int(np.argmax(lg))
    with open(os.path.join(VEC, "meta_%d.txt" % k), "w",
              encoding="ascii", newline="\n") as f:
        f.write("index %d\nlabel %d\nargmax %d\n" % (-1, label, am))
    print("vector %d: argmax %d  logits %s" % (k, am, [int(v) for v in lg]))


def check():
    ok = True
    for k in range(8):
        img = rdb(os.path.join(VEC, "img_%d.hex" % k))
        c1, p1, c2, p2, fc1, lg = model(img)
        for name, got in (("c1", c1), ("p1", p1), ("c2", c2), ("p2", p2),
                          ("fc1", fc1)):
            exp = rdb(os.path.join(VEC, "exp_%s_%d.hex" % (name, k)))
            good = np.array_equal(got.reshape(-1).astype(np.uint8), exp)
            ok &= good
            if not good:
                bad = np.where(got.reshape(-1).astype(np.uint8) != exp)[0]
                print("vec %d %s FAIL n=%d first %d: got %d exp %d"
                      % (k, name, len(bad), bad[0],
                         got.reshape(-1)[bad[0]], exp[bad[0]]))
        exp_lg = [int(x, 16) for x in open(os.path.join(VEC, "logit_%d.hex" % k)) if x.strip()]
        got_lg = [int(v) & 0xFFFFFFFF for v in lg]   # files store uint32
        lg_ok = exp_lg == got_lg
        ok &= lg_ok
        if not lg_ok:
            print("vec %d logits FAIL got %s exp %s" % (k, got_lg, exp_lg))
        print("vec %d: %s" % (k, "OK" if (lg_ok and ok) else "see above"))
    print("REFERENCE MODEL %s" % ("VALID (bit-exact on all 8 vectors)" if ok else "INVALID"))
    return 0 if ok else 1


def mnist_test_images():
    import gzip
    path = os.path.join(HERE, "..", "MNIST", "t10k-images-idx3-ubyte.gz")
    with gzip.open(path, "rb") as f:
        data = f.read()
    n = int.from_bytes(data[4:8], "big")
    imgs = np.frombuffer(data, dtype=np.uint8, offset=16).reshape(n, 28, 28)
    lpath = os.path.join(HERE, "..", "MNIST", "t10k-labels-idx1-ubyte.gz")
    with gzip.open(lpath, "rb") as f:
        lab = np.frombuffer(f.read(), dtype=np.uint8, offset=8)
    return imgs, lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--make", nargs="+", type=int)
    a = ap.parse_args()
    if a.check:
        raise SystemExit(check())
    if a.make:
        used = set()
        for k in range(8):
            for line in open(os.path.join(VEC, "meta_%d.txt" % k)):
                if line.startswith("index"):
                    used.add(int(line.split()[1]))
        imgs, lab = mnist_test_images()
        plan = {
            8:  np.zeros((28, 28), dtype=np.uint8),
            9:  np.full((28, 28), 255, dtype=np.uint8),
            10: np.random.RandomState(74).randint(0, 256, (28, 28)).astype(np.uint8),
        }
        # 11..: one unused test image per still-missing digit (8, 9, ...)
        have = set()
        for k in range(8):
            for line in open(os.path.join(VEC, "meta_%d.txt" % k)):
                if line.startswith("label"):
                    have.add(int(line.split()[1]))
        want = [d for d in range(10) if d not in have]
        pool = {d: [i for i in range(len(lab)) if int(lab[i]) == d and i not in used]
                for d in want}
        wi = 0
        for k in a.make:
            if k in plan:
                write_vec(k, plan[k])
                continue
            d = want[wi % len(want)] if want else None
            wi += 1
            if not pool.get(d):
                raise SystemExit("no unused test image for digit %d" % d)
            idx = pool[d].pop(0)
            write_vec(k, imgs[idx], label=int(lab[idx]))
            print("  (test image idx %d, label %d)" % (idx, lab[idx]))
            used.add(idx)


if __name__ == "__main__":
    main()
