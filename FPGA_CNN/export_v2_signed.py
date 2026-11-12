"""Export the V2 signed-int8 model (scheme C) for the 74-series board.

V2 contract (docs/REQUANT_SIMPLE_V2.md):
    zero point 0 everywhere, no bias, one power-of-two shift per layer,
    Q = clamp(ACC >> S, 0, 255); FC2 keeps the raw signed int32 accumulator.

Scheme C hardware: the 8x8 LUT computes a * int8(b) as a 16-bit two's-
complement product and the accumulator chain sign-extends PSUM17 (BM17) into
ACC[31:17]  ->  the sum tree is a true signed accumulator.

Outputs (same file names/layout as weights/x28 so tb_numeric.v can use them):
    weights/x28s/{conv1,conv2,fc1,fc2}_{weight,bias}.hex
    weights/x28s/qparams.hex, model.bin, metadata.json
    weights/x28s/vectors/img_k.hex, logit_k.hex, meta_k.txt, labels.txt

Usage:
    python export_v2_signed.py [--limit 10000]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_export as T  # noqa: E402

ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "MNIST")
CKPT = os.path.join(HERE, "cnn28_fp32.pt")
SRC = os.path.join(ROOT, "weights", "x28")
OUT = os.path.join(ROOT, "weights", "x28s")


def im2col(x: np.ndarray, k: int) -> np.ndarray:
    n, ic, h, w = x.shape
    oh, ow = h - k + 1, w - k + 1
    win = np.lib.stride_tricks.sliding_window_view(x, (k, k), axis=(2, 3))
    return (win.transpose(0, 2, 3, 1, 4, 5)
               .reshape(n * oh * ow, ic * k * k)
               .astype(np.int32))


def pool2(x):
    return np.maximum(np.maximum(x[:, :, 0::2, 0::2], x[:, :, 0::2, 1::2]),
                      np.maximum(x[:, :, 1::2, 0::2], x[:, :, 1::2, 1::2]))


def write_hex(path, values, digits=2):
    with open(path, "w", encoding="ascii", newline="\n") as f:
        for v in values:
            f.write(f"{int(v) & ((1 << (4 * digits)) - 1):0{digits}x}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10000)
    ap.add_argument("--calib", type=int, default=2000)
    args = ap.parse_args()

    import torch

    xtr, ytr, xte, yte = T.load_mnist(DATA)
    xte, yte = xte[:args.limit], yte[:args.limit]

    model = T.build_model()
    model.load_state_dict(torch.load(CKPT, map_location="cpu"))
    model.eval()
    with torch.no_grad():
        fl = model(torch.from_numpy(xte).float().unsqueeze(1) / 255.0).numpy()
    print(f"float acc: {(fl.argmax(1) == yte).mean():.4f}")

    sd = model.state_dict()
    names = {"conv1": "0.weight", "conv2": "3.weight", "fc1": "7.weight", "fc2": "9.weight"}
    shapes = {"conv1": (8, 1, 5, 5), "conv2": (16, 8, 3, 3), "fc1": (32, 400), "fc2": (10, 32)}

    # ---- symmetric int8 quantization (s_w = max|w| / 127)
    qw = {}
    for nm, key in names.items():
        w = sd[key].numpy()
        s_w = max(float(np.abs(w).max()), 1e-12) / 127.0
        q = np.clip(np.round(w / s_w), -127, 127).astype(np.int8)
        qw[nm] = q.reshape(shapes[nm])
    print("weight ranges:", {k: (int(v.min()), int(v.max())) for k, v in qw.items()})

    # ---- calibrate one shift per layer on the training set (V2 rule)
    a = xtr[:args.calib].astype(np.uint8)[:, None, :, :]
    S = {}
    for nm, k in (("conv1", 5), ("conv2", 3), ("fc1", 0), ("fc2", 0)):
        q = qw[nm]
        if k:
            pmat = im2col(a, k)
            acc = pmat @ q.reshape(q.shape[0], -1).astype(np.int32).T
            amax = float(np.abs(acc).max())
            S[nm] = max(1, int(np.floor(np.log2(amax / 255.0)))) if amax > 1 else 1
            out = np.clip(acc >> S[nm], 0, 255)
            oh = a.shape[2] - k + 1
            a = out.reshape(a.shape[0], oh, oh, q.shape[0]).transpose(0, 3, 1, 2)
            a = pool2(a).astype(np.uint8)
        else:
            v = a.reshape(a.shape[0], -1).astype(np.int32)
            acc = v @ q.astype(np.int32).T
            amax = float(np.abs(acc).max())
            if nm == "fc2":
                S[nm] = 0
            else:
                S[nm] = max(1, int(np.floor(np.log2(amax / 255.0)))) if amax > 1 else 1
                a = np.clip(acc >> S[nm], 0, 255).astype(np.uint8)
    print("shifts:", S)
    if (S["conv1"], S["conv2"], S["fc1"]) != (9, 10, 9):
        print("WARNING: calibrated shifts differ from the board wiring 9/10/9")

    # ---- integer V2 inference (bit-exact target for the testbench)
    def infer(xb):
        a = xb[:, None, :, :]
        for nm, k in (("conv1", 5), ("conv2", 3)):
            q = qw[nm]
            pmat = im2col(a, k)
            acc = pmat @ q.reshape(q.shape[0], -1).astype(np.int32).T
            out = np.clip(acc >> S[nm], 0, 255)
            oh = a.shape[2] - k + 1
            a = out.reshape(a.shape[0], oh, oh, q.shape[0]).transpose(0, 3, 1, 2)
            a = pool2(a).astype(np.uint8)
        v = a.reshape(a.shape[0], -1).astype(np.int32)
        acc = v @ qw["fc1"].astype(np.int32).T
        a = np.clip(acc >> S["fc1"], 0, 255).astype(np.uint8)
        v = a.reshape(a.shape[0], -1).astype(np.int32)
        return v @ qw["fc2"].astype(np.int32).T

    logits = np.concatenate([infer(xte[i:i + 500].astype(np.uint8))
                             for i in range(0, len(xte), 500)], axis=0)
    acc_v2 = float((logits.argmax(1) == yte).mean())
    print(f"V2 signed int8 acc: {acc_v2:.4f}  (limit={len(yte)})")

    # ---- export
    os.makedirs(os.path.join(OUT, "vectors"), exist_ok=True)
    sect = {}
    blob = bytearray()

    def put(name, arr, digits):
        write_hex(os.path.join(OUT, f"{name}.hex"), arr, digits)

    for nm in ("conv1", "conv2", "fc1", "fc2"):
        w = qw[nm].reshape(-1).astype(np.int8)
        bias = np.zeros((qw[nm].shape[0],), dtype=np.int32)   # V2: no bias
        sect[f"{nm}_weight"] = len(blob); blob += w.tobytes()
        sect[f"{nm}_bias"] = len(blob); blob += bias.astype("<i4").tobytes()
        put(f"{nm}_weight", w, 2)
        put(f"{nm}_bias", bias, 8)

    # qparam records: same 16-byte layout, M=1, S=layer shift (informational only)
    qrec = bytearray()
    for nm in ("conv1", "conv2", "fc1", "fc2"):
        relu = 0 if nm == "fc2" else 1
        int32_out = 1 if nm == "fc2" else 0
        for _ in range(qw[nm].shape[0]):
            rec = bytearray(16)
            rec[0] = 0
            rec[1] = 0                     # zp_w = 0 (signed weights)
            rec[2] = 0
            rec[3] = relu | (int32_out << 1)
            rec[4:8] = struct.pack("<I", 1)   # M = 1 (pure shift)
            rec[8] = S[nm]
            qrec += rec
    sect["qparams"] = len(blob); blob += qrec
    write_hex(os.path.join(OUT, "qparams.hex"), [b for b in qrec], 2)
    with open(os.path.join(OUT, "qparams.bin"), "wb") as f:
        f.write(qrec)
    with open(os.path.join(OUT, "model.bin"), "wb") as f:
        f.write(blob)
    meta = {"source": "export_v2_signed.py", "sections": sect,
            "model_bin_bytes": len(blob), "shifts": S,
            "quant": "symmetric int8, zp=0, no bias, arithmetic >>S"}
    with open(os.path.join(OUT, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # ---- vectors: same image picks as x28, new expected logits
    labels = []
    for k in range(8):
        m = os.path.join(SRC, "vectors", f"meta_{k}.txt")
        if not os.path.exists(m):
            break
        info = dict(line.split() for line in open(m, encoding="utf-8"))
        idx = int(info["index"])
        img = xte[idx] if idx < len(xte) else T.load_mnist(DATA)[2][idx]
        logit = infer(img[None].astype(np.uint8))[0]
        shutil.copyfile(os.path.join(SRC, "vectors", f"img_{k}.hex"),
                        os.path.join(OUT, "vectors", f"img_{k}.hex"))
        write_hex(os.path.join(OUT, "vectors", f"logit_{k}.hex"),
                  [int(v) & 0xFFFFFFFF for v in logit], 8)
        with open(os.path.join(OUT, "vectors", f"meta_{k}.txt"), "w",
                  encoding="utf-8") as f:
            f.write(f"index {idx}\nlabel {int(yte[idx])}\n"
                    f"argmax {int(np.argmax(logit))}\n")
        labels.append(int(yte[idx]))
        print(f"  vector {k}: idx={idx} label={yte[idx]} argmax={int(np.argmax(logit))} "
              f"logits={[int(v) for v in logit]}")
    with open(os.path.join(OUT, "vectors", "labels.txt"), "w", encoding="ascii") as f:
        f.writelines(f"{v}\n" for v in labels)

    print(f"written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
