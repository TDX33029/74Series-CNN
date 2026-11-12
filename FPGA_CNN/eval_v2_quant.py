"""Quantify the accuracy cost of the 74-series "V2" quantization contract.

V2 (docs/REQUANT_SIMPLE_V2.md):
    ZP_X = ZP_W = ZP_OUT = 0, bias = 0,
    one power-of-two output scale per layer:  Q = clamp(ACC >> S, 0, 255),
    plain arithmetic shift, no rounding.

The trained checkpoint was produced under a different contract
(per-channel M/S + int32 bias).  This script measures, on the same float
weights and without retraining, how much accuracy each simplification costs:

    float      raw float model                                (reference)
    int8       current contract: zp_w=128, per-channel M/S, bias, rounding
    no-bias    current contract but bias forced to 0
    uniform    per-channel M/S collapsed to one M/S per layer
    v2         zero bias + per-tensor symmetric int8 + plain >>S

Usage:  python eval_v2_quant.py [--limit N] [--calib N]
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_export as T  # noqa: E402

CKPT = os.path.join(HERE, "cnn28_fp32.pt")
DATA = os.path.join(os.path.dirname(HERE), "MNIST")


# ---------------------------------------------------------------- helpers
def im2col(x: np.ndarray, k: int) -> np.ndarray:
    """x (N,IC,H,W) uint8 -> (N*OH*OW, IC*K*K) float32 (exact integers)."""
    n, ic, h, w = x.shape
    oh, ow = h - k + 1, w - k + 1
    win = np.lib.stride_tricks.sliding_window_view(x, (k, k), axis=(2, 3))
    return (win.transpose(0, 2, 3, 1, 4, 5)
               .reshape(n * oh * ow, ic * k * k)
               .astype(np.float32))


def requant(acc: np.ndarray, m, s, round_: bool, relu: bool) -> np.ndarray:
    """acc (exact integers) -> float64 quantized values."""
    a = np.asarray(acc, dtype=np.float64) * np.asarray(m, dtype=np.float64)
    sf = np.asarray(s, dtype=np.float64)
    if round_:
        a = a + np.power(2.0, sf - 1.0)
    a = np.floor(a / np.power(2.0, sf))
    if relu:
        a = np.clip(a, 0, 255)
    return a


def conv_fwd(x, w, k, m, s, bias=None, zp_w=None, round_=True, relu=True):
    n, ic, h, wd = x.shape
    oh, ow = h - k + 1, wd - k + 1
    p = im2col(x, k)
    oc = w.shape[0]
    acc = p @ w.reshape(oc, -1).astype(np.float32).T
    if zp_w is not None:
        acc = acc - zp_w * p.sum(axis=1, dtype=np.float32)[:, None]
    if bias is not None:
        acc = acc + bias[None, :]
    q = requant(acc, m, s, round_, relu)
    return q.reshape(n, oh, ow, oc).transpose(0, 3, 1, 2)


def fc_fwd(x, w, m, s, bias=None, zp_w=None, round_=True, relu=True):
    v = x.reshape(x.shape[0], -1).astype(np.float32)
    acc = v @ w.astype(np.float32).T
    if zp_w is not None:
        acc = acc - zp_w * v.sum(axis=1, keepdims=True)
    if bias is not None:
        acc = acc + bias[None, :]
    return requant(acc, m, s, round_, relu)


def pool2(x):
    return np.maximum(np.maximum(x[:, :, 0::2, 0::2], x[:, :, 0::2, 1::2]),
                      np.maximum(x[:, :, 1::2, 0::2], x[:, :, 1::2, 1::2]))


# ------------------------------------------------------------------ model
def build_p(model):
    """Reproduce train_export.main(): the parameters actually in model.bin."""
    sd = model.state_dict()
    xtr = None
    return sd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="test images (0 = all 10000)")
    ap.add_argument("--calib", type=int, default=2000)
    ap.add_argument("--shifts", default="",
                    help="force V2 shifts as C1,C2,FC1 (e.g. 8,9,8); "
                         "default = calibrate from the weights")
    args = ap.parse_args()

    import torch
    xtr, ytr, xte, yte = T.load_mnist(DATA)
    if args.limit:
        xte, yte = xte[:args.limit], yte[:args.limit]

    model = T.build_model()
    model.load_state_dict(torch.load(CKPT, map_location="cpu"))
    model.eval()
    sd = model.state_dict()

    # ---- float reference
    with torch.no_grad():
        fl = model(torch.from_numpy(xte).float().unsqueeze(1) / 255.0).numpy()
    acc_float = float((fl.argmax(1) == yte).mean())

    # ---- activation scales (same as the exporter)
    acts = T.calibrate(model, xtr)
    s_in = 1.0 / 255.0
    s_out = {k: max(v, 1e-9) / 255.0 for k, v in acts.items()}
    s_out["fc2"] = 1.0

    p = {}
    p["conv1"] = T.quantize_layer(sd["0.weight"].numpy(), sd["0.bias"].numpy(),
                                  s_in, s_out["conv1"])
    p["conv2"] = T.quantize_layer(sd["3.weight"].numpy(), sd["3.bias"].numpy(),
                                  s_out["conv1"], s_out["conv2"])
    p["fc1"] = T.quantize_layer(sd["7.weight"].numpy(), sd["7.bias"].numpy(),
                                s_out["conv2"], s_out["fc1"])
    p["fc2"] = T.quantize_layer(sd["9.weight"].numpy(), sd["9.bias"].numpy(),
                                s_out["fc1"], 1.0)
    s_logit = float(np.max(p["fc2"]["s_acc"]))
    M2, S2 = [], []
    for c in range(10):
        m, s = T.pick_ms(float(p["fc2"]["s_acc"][c] / s_logit))
        M2.append(m)
        S2.append(s)
    p["fc2"]["M"] = np.array(M2)
    p["fc2"]["S"] = np.array(S2)

    def run(mode, xb):
        a = xb[:, None, :, :]
        for nm, k in (("conv1", 5), ("conv2", 3)):
            lay = p[nm]
            bias = np.zeros_like(lay["bias32"]) if mode == "no-bias" else lay["bias32"]
            m, s = lay["M"], lay["S"]
            if mode == "uniform":
                ratio = float(np.median(lay["s_acc"] / s_out[nm]))
                mm, ss = T.pick_ms(ratio)
                m, s = np.full(len(m), mm), np.full(len(s), ss)
            a = conv_fwd(a, lay["w_u8"], k, m, s, bias=bias, zp_w=128,
                         round_=True, relu=True)
            a = pool2(a)
        for nm in ("fc1", "fc2"):
            lay = p[nm]
            bias = np.zeros_like(lay["bias32"]) if mode == "no-bias" else lay["bias32"]
            m, s = lay["M"], lay["S"]
            if mode == "uniform":
                ratio = float(np.median(lay["s_acc"] / (s_logit if nm == "fc2" else s_out[nm])))
                mm, ss = T.pick_ms(ratio)
                m, s = np.full(len(m), mm), np.full(len(s), ss)
            a = fc_fwd(a, lay["w_u8"], m, s, bias=bias, zp_w=128,
                       round_=True, relu=(nm != "fc2"))
        return a

    def collect(fn):
        out = []
        for i in range(0, len(xte), 1000):
            out.append(fn(xte[i:i + 1000]))
        return np.concatenate(out, axis=0)

    acc_int8 = float((collect(lambda xb: run("int8", xb)).argmax(1) == yte).mean())
    acc_nobias = float((collect(lambda xb: run("no-bias", xb)).argmax(1) == yte).mean())
    acc_uniform = float((collect(lambda xb: run("uniform", xb)).argmax(1) == yte).mean())

    # ---- V2: zero bias, per-tensor symmetric int8, plain arithmetic shift
    print("V2 calibration ...", flush=True)
    xcal = xtr[:args.calib].astype(np.uint8)
    v2 = {}
    a = xcal[:, None, :, :]
    forced = {}
    if args.shifts:
        c1, c2, f1 = (int(v) for v in args.shifts.split(","))
        forced = {"conv1": c1, "conv2": c2, "fc1": f1}
    for nm, k in (("conv1", 5), ("conv2", 3), ("fc1", 0), ("fc2", 0)):
        w = sd[{"conv1": "0.weight", "conv2": "3.weight",
                "fc1": "7.weight", "fc2": "9.weight"}[nm]].numpy()
        s_w = float(np.abs(w).max()) / 127.0
        qw = np.clip(np.round(w / s_w), -127, 127).astype(np.int32)
        if k:
            pmat = im2col(a, k)
            acc = pmat @ qw.reshape(qw.shape[0], -1).astype(np.float32).T
            oh = a.shape[2] - k + 1
        else:
            acc = a.reshape(a.shape[0], -1).astype(np.float32) @ qw.astype(np.float32).T
            oh = 0
        amax = float(np.abs(acc).max())
        if nm == "fc2":
            sh = 0
        elif nm in forced:
            sh = forced[nm]
        else:
            sh = max(1, int(np.floor(np.log2(amax / 255.0)))) if amax > 1 else 1
        v2[nm] = (qw, sh, k)
        print(f"  {nm:5s} |acc|max={amax:10.3g}  S={sh:2d}")
        q = requant(acc, 1, sh, round_=False, relu=(nm != "fc2"))
        if k:
            a = q.reshape(a.shape[0], oh, oh, qw.shape[0]).transpose(0, 3, 1, 2)
            a = pool2(a).astype(np.uint8)
        else:
            a = q.astype(np.uint8) if nm != "fc2" else q

    def v2_infer(xb):
        a = xb[:, None, :, :]
        for nm, k in (("conv1", 5), ("conv2", 3), ("fc1", 0), ("fc2", 0)):
            qw, sh, _ = v2[nm]
            if k:
                pmat = im2col(a, k)
                acc = pmat @ qw.reshape(qw.shape[0], -1).astype(np.float32).T
                oh = a.shape[2] - k + 1
                q = requant(acc, 1, sh, round_=False, relu=True)
                a = pool2(q.reshape(a.shape[0], oh, oh, qw.shape[0])
                           .transpose(0, 3, 1, 2)).astype(np.uint8)
            else:
                acc = a.reshape(a.shape[0], -1).astype(np.float32) @ qw.astype(np.float32).T
                a = requant(acc, 1, sh, round_=False, relu=(nm != "fc2"))
        return a

    acc_v2 = float((collect(v2_infer).argmax(1) == yte).mean())

    n = len(yte)
    print(f"\n=== MNIST test set ({n} images) ===")
    print(f"  float                                {acc_float*100:6.2f} %")
    print(f"  int8 (current contract)              {acc_int8*100:6.2f} %")
    print(f"  no bias                              {acc_nobias*100:6.2f} %  "
          f"({(acc_nobias-acc_int8)*100:+.2f} pp)")
    print(f"  uniform M/S per layer                {acc_uniform*100:6.2f} %  "
          f"({(acc_uniform-acc_int8)*100:+.2f} pp)")
    print(f"  V2 (no bias + uniform + truncation)  {acc_v2*100:6.2f} %  "
          f"({(acc_v2-acc_int8)*100:+.2f} pp)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
