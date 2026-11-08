"""Train the 28x28 MNIST CNN from CNN_74xx_MNIST_28x28_v1.txt and export
uint8 affine-quantized parameters for the FPGA implementation.

Topology (VALID conv, no padding, 2x2/2 max pool):

    28x28x1 -> Conv 5x5 1->8  -> ReLU -> Pool -> 12x12x8
            -> Conv 3x3 8->16 -> ReLU -> Pool -> 5x5x16 (400)
            -> FC 400->32 -> ReLU -> FC 32->10 -> argmax

Quantization contract (doc section 2.5), identical to the 74-series hardware:

    q_x  uint8, zp_x = 0            (input pixel = round(real*255))
    q_w  uint8 = w_int8 + 128, zp_w = 128, symmetric per output channel
    ACC  = SUM(q_x*q_w) - zp_w*SUM(q_x) + bias_int32
    q_out= clamp( (ACC*M + 2^(S-1)) >> S , 0, 255 )
    FC2  : logit = (ACC*M + 2^(S-1)) >> S on a common scale, no clamp

Usage:
    python train_export.py                     # train + export
    python train_export.py --epochs 16         # longer training
    python train_export.py --skip-train        # re-export from checkpoint
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DATA = os.path.join(ROOT, "MNIST")
DEFAULT_OUT = os.path.join(ROOT, "weights", "x28")
CKPT = os.path.join(HERE, "cnn28_fp32.pt")

# layer geometry, doc section 1
CONV1 = dict(IC=1, OC=8, K=5, H=28, W=28)
POOL1 = dict(OH=12, OW=12, OC=8)
CONV2 = dict(IC=8, OC=16, K=3, H=12, W=12)
POOL2 = dict(OH=5, OW=5, OC=16)
FC1 = dict(NIN=400, NOUT=32)
FC2 = dict(NIN=32, NOUT=10)


# ---------------------------------------------------------------- dataset
def read_idx_images(path: str) -> np.ndarray:
    with open(path, "rb") as f:
        magic, num, rows, cols = struct.unpack(">IIII", f.read(16))
        assert magic == 2051, magic
        return np.frombuffer(f.read(), np.uint8).reshape(num, rows, cols)


def read_idx_labels(path: str) -> np.ndarray:
    with open(path, "rb") as f:
        magic, num = struct.unpack(">II", f.read(8))
        assert magic == 2049, magic
        return np.frombuffer(f.read(), np.uint8)


def load_mnist(data_dir: str):
    def p(sub, name):
        return os.path.join(data_dir, sub, name)

    xtr = read_idx_images(p("train-images-idx3-ubyte", "train-images.idx3-ubyte"))
    ytr = read_idx_labels(p("train-labels-idx1-ubyte", "train-labels.idx1-ubyte"))
    xte = read_idx_images(p("t10k-images-idx3-ubyte", "t10k-images.idx3-ubyte"))
    yte = read_idx_labels(p("t10k-labels-idx1-ubyte", "t10k-labels.idx1-ubyte"))
    return xtr, ytr, xte, yte


# ------------------------------------------------------------------ model
def build_model():
    import torch.nn as nn

    return nn.Sequential(
        nn.Conv2d(1, 8, 5), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(8, 16, 3), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(400, 32), nn.ReLU(),
        nn.Linear(32, 10),
    )


def train(xtr, ytr, xte, yte, epochs: int, batch: int, seed: int) -> None:
    import torch
    import torch.nn as nn
    import torch.optim as optim

    torch.manual_seed(seed)
    np.random.seed(seed)

    model = build_model()
    opt = optim.Adam(model.parameters(), lr=1e-3)
    sched = optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    lossf = nn.CrossEntropyLoss()

    xt = torch.from_numpy(xtr).float().unsqueeze(1) / 255.0
    yt = torch.from_numpy(ytr).long()
    xv = torch.from_numpy(xte).float().unsqueeze(1) / 255.0
    yv = torch.from_numpy(yte).long()

    n = len(xt)
    for ep in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(n)
        tot = 0.0
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            opt.zero_grad()
            out = model(xt[idx])
            loss = lossf(out, yt[idx])
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        sched.step()
        model.eval()
        with torch.no_grad():
            acc = 0
            for i in range(0, len(xv), 1000):
                pred = model(xv[i:i + 1000]).argmax(1)
                acc += (pred == yv[i:i + 1000]).sum().item()
        print(f"epoch {ep:2d}/{epochs}  loss {tot / n:.4f}  test acc {acc / len(xv):.4f}",
              flush=True)
        torch.save(model.state_dict(), CKPT)
    return model


# ------------------------------------------------------------ calibration
def calibrate(model, xtr, limit=20000):
    """Per-layer activation maxima over a training subset (float model)."""
    import torch

    acts = {"conv1": 0.0, "conv2": 0.0, "fc1": 0.0}
    hooks = []

    def hook(name):
        def fn(_m, _i, out):
            m = float(out.detach().max())
            acts[name] = max(acts[name], m)
        return fn

    seq = model
    hooks.append(seq[0].register_forward_hook(hook("conv1")))
    hooks.append(seq[3].register_forward_hook(hook("conv2")))
    hooks.append(seq[7].register_forward_hook(hook("fc1")))

    model.eval()
    with torch.no_grad():
        for i in range(0, min(limit, len(xtr)), 1000):
            x = torch.from_numpy(xtr[i:i + 1000]).float().unsqueeze(1) / 255.0
            model(x)
    for h in hooks:
        h.remove()
    return acts


# ------------------------------------------------------------ quantization
def pick_ms(ratio: float) -> tuple[int, int]:
    """Return (M, S) with M in [32768, 65535] and ratio ~= M / 2^S."""
    assert ratio > 0
    s = int(np.floor(np.log2(65535.0 / ratio)))
    s = max(s, 1)
    m = int(round(ratio * (1 << s)))
    while m > 65535:
        s -= 1
        m = int(round(ratio * (1 << s)))
    assert 1 <= m <= 65535, (ratio, m, s)
    assert s <= 63, (ratio, m, s)
    return m, s


def quantize_layer(w: np.ndarray, b: np.ndarray, s_in: float,
                   s_out: float) -> dict:
    """w: (OC, ...) float, b: (OC,) float -> uint8 weights, int32 bias, M/S."""
    w = w.astype(np.float64)
    oc = w.shape[0]
    flat = w.reshape(oc, -1)
    maxabs = np.abs(flat).max(axis=1)
    maxabs[maxabs == 0] = 1e-12
    s_w = maxabs / 127.0
    q = np.clip(np.round(flat / s_w[:, None]), -127, 127).astype(np.int32)
    q_u8 = (q + 128).astype(np.uint8)
    s_acc = s_in * s_w
    b_q = np.round(b / s_acc).astype(np.int64)
    assert np.all(np.abs(b_q) < 2**31), b_q
    M, S = [], []
    for c in range(oc):
        m, s = pick_ms(float(s_acc[c] / s_out))
        M.append(m)
        S.append(s)
    return dict(w_u8=q_u8, w_int8=q, s_w=s_w, s_acc=s_acc,
                bias32=b_q.astype(np.int32), M=np.array(M), S=np.array(S))


# ------------------------------------------------------------- gold model
def _conv_u8(x, q, bias, M, S, K):
    """x (IC,H,W) uint8 -> (OC,OH,OW) uint8, integer-exact."""
    ic, h, w = x.shape
    oc = q.shape[0]
    oh, ow = h - K + 1, w - K + 1
    win = np.lib.stride_tricks.sliding_window_view(x, (K, K), axis=(1, 2))
    # (IC, OH, OW, K, K) -> (OH*OW, IC*K*K)
    p = win.transpose(1, 2, 0, 3, 4).reshape(oh * ow, ic * K * K).astype(np.int32)
    wm = q.reshape(oc, -1).astype(np.int32)
    raw = p @ wm.T                                   # (OH*OW, OC)
    sx = p.sum(axis=1, dtype=np.int32)               # (OH*OW,)
    acc = raw - 128 * sx[:, None] + bias[None, :]
    acc64 = acc.astype(np.int64)
    out = (acc64 * M[None, :] + (1 << (S[None, :] - 1))) >> S[None, :]
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out.reshape(oh, ow, oc).transpose(2, 0, 1)


def _pool2(x):
    return np.maximum(np.maximum(x[:, 0::2, 0::2], x[:, 0::2, 1::2]),
                      np.maximum(x[:, 1::2, 0::2], x[:, 1::2, 1::2]))


def _fc_u8(x, q, bias, M, S, relu=True):
    v = x.reshape(-1).astype(np.int32)
    raw = q.astype(np.int32) @ v                  # (NOUT,)
    sx = int(v.sum(dtype=np.int32))
    acc = raw - 128 * sx + bias                   # (NOUT,)
    acc64 = acc.astype(np.int64)
    out = (acc64 * M + (1 << (S - 1))) >> S
    if relu:
        out = np.clip(out, 0, 255)
    return out


def gold_infer(img: np.ndarray, p: dict) -> np.ndarray:
    """img: (28,28) uint8 -> 10 int32 logits."""
    x = img[None, :, :]                            # (1,28,28)
    a = _conv_u8(x, p["conv1"]["w_u8"], p["conv1"]["bias32"],
                 p["conv1"]["M"], p["conv1"]["S"], CONV1["K"])
    a = _pool2(a)
    a = _conv_u8(a, p["conv2"]["w_u8"], p["conv2"]["bias32"],
                 p["conv2"]["M"], p["conv2"]["S"], CONV2["K"])
    a = _pool2(a)
    a = _fc_u8(a, p["fc1"]["w_u8"], p["fc1"]["bias32"],
               p["fc1"]["M"], p["fc1"]["S"], relu=True)
    logits = _fc_u8(a, p["fc2"]["w_u8"], p["fc2"]["bias32"],
                    p["fc2"]["M"], p["fc2"]["S"], relu=False)
    return logits.astype(np.int32)


def eval_gold(model, xte, yte, p):
    ok = 0
    conf = np.zeros((10, 10), np.int64)
    for i in range(len(xte)):
        logits = gold_infer(xte[i], p)
        pred = int(np.argmax(logits))
        ok += pred == yte[i]
        conf[yte[i], pred] += 1
    return ok / len(xte), conf


# ---------------------------------------------------------------- export
def write_txt(path, values):
    with open(path, "w", encoding="ascii") as f:
        for v in values:
            f.write(f"{int(v)}\n")


def write_hex(path, values, digits):
    with open(path, "w", encoding="ascii") as f:
        for v in values:
            f.write(f"{int(v) & ((1 << (4 * digits)) - 1):0{digits}x}\n")


def qparam_records(p: dict) -> bytes:
    """66 x 16-byte records, doc section 3.4 layout."""
    out = bytearray()
    for name in ("conv1", "conv2", "fc1", "fc2"):
        lay = p[name]
        relu = 0 if name == "fc2" else 1
        int32_out = 1 if name == "fc2" else 0
        for c in range(len(lay["M"])):
            rec = bytearray(16)
            rec[0] = 0                       # input zero point
            rec[1] = 128                     # weight zero point
            rec[2] = 0                       # output zero point
            rec[3] = relu | (int32_out << 1) # flags
            rec[4:8] = struct.pack("<I", int(lay["M"][c]))
            rec[8] = int(lay["S"][c])
            out += rec
    return bytes(out)


def export(p: dict, meta: dict, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    files = {}

    for name in ("conv1", "conv2", "fc1", "fc2"):
        lay = p[name]
        wtxt = os.path.join(out_dir, f"{name}_weight.txt")
        btxt = os.path.join(out_dir, f"{name}_bias.txt")
        write_txt(wtxt, lay["w_u8"].reshape(-1))
        write_txt(btxt, lay["bias32"])
        write_hex(os.path.join(out_dir, f"{name}_weight.hex"),
                  lay["w_u8"].reshape(-1), 2)
        write_hex(os.path.join(out_dir, f"{name}_bias.hex"), lay["bias32"], 8)
        files[f"{name}_weight"] = int(lay["w_u8"].size)
        files[f"{name}_bias"] = int(lay["bias32"].size)

    qrec = qparam_records(p)
    write_hex(os.path.join(out_dir, "qparams.hex"),
              [qrec[i] for i in range(len(qrec))], 2)
    with open(os.path.join(out_dir, "qparams.bin"), "wb") as f:
        f.write(qrec)
    files["qparams"] = len(qrec)

    # one binary blob for the host download, sections in this fixed order
    blob = bytearray()
    offsets = {}
    for name in ("conv1", "conv2", "fc1", "fc2"):
        offsets[f"{name}_weight"] = len(blob)
        blob += p[name]["w_u8"].tobytes()
        offsets[f"{name}_bias"] = len(blob)
        blob += p[name]["bias32"].astype("<i4").tobytes()
    offsets["qparams"] = len(blob)
    blob += qrec
    with open(os.path.join(out_dir, "model.bin"), "wb") as f:
        f.write(blob)

    meta = dict(meta)
    meta["sections"] = offsets
    meta["model_bin_bytes"] = len(blob)
    with open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return {"files": files, "blob": len(blob), "offsets": offsets}


# --------------------------------------------------------- test vectors
def export_vectors(p: dict, xte, yte, out_dir: str, count=8) -> None:
    vdir = os.path.join(out_dir, "vectors")
    os.makedirs(vdir, exist_ok=True)
    # pick the first image of each class plus a couple of hard ones
    picks = []
    for cls in range(10):
        idx = int(np.nonzero(yte == cls)[0][0])
        picks.append(idx)
    picks = picks[:count]
    for k, idx in enumerate(picks):
        img = xte[idx]
        logits = gold_infer(img, p)
        write_hex(os.path.join(vdir, f"img_{k}.hex"),
                  img.reshape(-1), 2)
        write_hex(os.path.join(vdir, f"logit_{k}.hex"),
                  [int(v) & 0xFFFFFFFF for v in logits], 8)
        with open(os.path.join(vdir, f"meta_{k}.txt"), "w") as f:
            f.write(f"index {idx}\nlabel {int(yte[idx])}\n"
                    f"argmax {int(np.argmax(logits))}\n")
    write_txt(os.path.join(vdir, "labels.txt"), [int(yte[i]) for i in picks])
    print(f"exported {len(picks)} test vectors to {vdir}")


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--vectors", type=int, default=8)
    args = ap.parse_args()

    xtr, ytr, xte, yte = load_mnist(args.data)
    print(f"train {xtr.shape} test {xte.shape}")

    import torch
    if args.skip_train:
        model = build_model()
        model.load_state_dict(torch.load(CKPT, map_location="cpu"))
        print(f"loaded {CKPT}")
    else:
        model = train(xtr, ytr, xte, yte, args.epochs, args.batch, args.seed)

    model.eval()
    with torch.no_grad():
        pred = model(torch.from_numpy(xte).float().unsqueeze(1) / 255.0).argmax(1)
        acc_f = (pred == torch.from_numpy(yte).long()).float().mean().item()

    acts = calibrate(model, xtr)
    print("activation maxima:", {k: round(v, 4) for k, v in acts.items()})

    s_in = 1.0 / 255.0
    s_out = {k: max(v, 1e-9) / 255.0 for k, v in acts.items()}
    s_out["fc2"] = 1.0     # placeholder, logits use a common scale

    sd = model.state_dict()
    p = {}
    p["conv1"] = quantize_layer(sd["0.weight"].numpy(), sd["0.bias"].numpy(),
                                s_in, s_out["conv1"])
    # conv2 reads the pool1 output, so its input scale is conv1's output scale
    p["conv2"] = quantize_layer(sd["3.weight"].numpy(), sd["3.bias"].numpy(),
                                s_out["conv1"], s_out["conv2"])
    p["fc1"] = quantize_layer(sd["7.weight"].numpy(), sd["7.bias"].numpy(),
                              s_out["conv2"], s_out["fc1"])
    p["fc2"] = quantize_layer(sd["9.weight"].numpy(), sd["9.bias"].numpy(),
                              s_out["fc1"], 1.0)

    # FC2: rescale every class to one common logit scale
    s_logit = float(np.max(p["fc2"]["s_acc"]))
    M2, S2 = [], []
    for c in range(FC2["NOUT"]):
        m, s = pick_ms(float(p["fc2"]["s_acc"][c] / s_logit))
        M2.append(m)
        S2.append(s)
    p["fc2"]["M"] = np.array(M2)
    p["fc2"]["S"] = np.array(S2)

    acc_q, conf = eval_gold(model, xte, yte, p)
    print(f"float accuracy {acc_f:.4f}")
    print(f"int8  accuracy {acc_q:.4f}  (delta {acc_q - acc_f:+.4f})")
    print("per-class accuracy:",
          {c: round(float(conf[c, c] / max(conf[c].sum(), 1)), 3) for c in range(10)})

    meta = {
        "topology": "28x28x1 - conv5x5(1->8) - relu - pool2 - "
                    "conv3x3(8->16) - relu - pool2 - fc(400->32) - relu - fc(32->10)",
        "input": {"scale": s_in, "zp": 0, "encoding": "pixel 0..255"},
        "layers": {},
        "accuracy_float": acc_f,
        "accuracy_int8": acc_q,
        "weight_encoding": "uint8 = int8 + 128, zp_w = 128",
        "requant": "out = (ACC*M + 2^(S-1)) >> S, M 16-bit, S 0..63",
        "layout": {
            "conv1": "oc*25 + ky*5 + kx",
            "conv2": "((oc*8 + ic)*3 + ky)*3 + kx",
            "fc1": "neuron*400 + input",
            "fc2": "class*32 + input",
            "bias": "neuron*4 + byte (int32 LE)",
        },
    }
    for name in ("conv1", "conv2", "fc1", "fc2"):
        lay = p[name]
        meta["layers"][name] = {
            "scale_in": float(s_in if name == "conv1" else
                              s_out["conv1"] if name == "conv2" else
                              s_out["conv2"] if name == "fc1" else s_out["fc1"]),
            "scale_out": float(s_out["conv1"] if name == "conv1" else
                               s_out["conv2"] if name == "conv2" else
                               s_out["fc1"] if name == "fc1" else s_logit),
            "M": [int(v) for v in lay["M"]],
            "S": [int(v) for v in lay["S"]],
            "s_w": [float(v) for v in lay["s_w"]],
        }

    info = export(p, meta, args.out)
    print(f"exported to {args.out}: {info['blob']} B model.bin, "
          f"{info['offsets']}")
    export_vectors(p, xte, yte, args.out, args.vectors)

    # keep the quantized arrays for a later re-export without retraining
    np.savez(os.path.join(HERE, "cnn28_quant.npz"),
             **{f"{n}_{k}": p[n][k] for n in p for k in ("w_u8", "bias32", "M", "S")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
