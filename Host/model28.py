"""Integer reference model of the 28x28 CNN (numpy only, no torch).

This mirrors FPGA_CNN/rtl/cnn28_core.v bit for bit:

    ACC  = SUM(q_x*q_w) - 128*SUM(q_x) + bias_int32
    q    = clamp((ACC*M + 2^(S-1)) >> S, 0, 255)      conv/pool/fc1
    FC2  : logit = (ACC*M + 2^(S-1)) >> S, int32, no clamp

It is used by the host in simulator mode and to validate the exported
parameter set.
"""
from __future__ import annotations

import json
import os

import numpy as np

GEOM = {
    "conv1": dict(IC=1, OC=8, K=5, H=28, W=28),
    "conv2": dict(IC=8, OC=16, K=3, H=12, W=12),
    "fc1": dict(NIN=400, NOUT=32),
    "fc2": dict(NIN=32, NOUT=10),
}


def load_model(model_dir: str) -> dict:
    """Load model.bin + metadata.json from an export directory."""
    with open(os.path.join(model_dir, "metadata.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(model_dir, "model.bin"), "rb") as f:
        blob = f.read()

    offs = sorted(meta["sections"].items(), key=lambda kv: kv[1])
    lens = {}
    for i, (name, off) in enumerate(offs):
        end = offs[i + 1][1] if i + 1 < len(offs) else len(blob)
        lens[name] = end - off

    def sec(name):
        off = meta["sections"][name]
        return blob[off:off + lens[name]]

    shap = {"conv1": (8, 25), "conv2": (16, 72),
            "fc1": (32, 400), "fc2": (10, 32)}
    m = {"meta": meta, "layers": {}}
    for name in ("conv1", "conv2", "fc1", "fc2"):
        w = np.frombuffer(sec(f"{name}_weight"), np.uint8).copy()
        w = w.reshape(shap[name])
        b = np.frombuffer(sec(f"{name}_bias"), "<i4").copy()
        lay = meta["layers"][name]
        m["layers"][name] = dict(
            w=w, bias=b, M=np.array(lay["M"], np.int64),
            S=np.array(lay["S"], np.int64))
    qp = np.frombuffer(sec("qparams"), np.uint8).copy()
    m["qparams"] = qp.reshape(-1, 16)
    return m


def _conv(x: np.ndarray, w: np.ndarray, bias: np.ndarray,
          M: np.ndarray, S: np.ndarray, oc: int, k: int) -> np.ndarray:
    ic, h, wd = x.shape
    oh, ow = h - k + 1, wd - k + 1
    win = np.lib.stride_tricks.sliding_window_view(x, (k, k), axis=(1, 2))
    p = win.transpose(1, 2, 0, 3, 4).reshape(oh * ow, ic * k * k).astype(np.int32)
    wm = w.reshape(oc, -1).astype(np.int32)
    raw = p @ wm.T
    sx = p.sum(axis=1, dtype=np.int32)
    acc = (raw.astype(np.int64) - 128 * sx[:, None].astype(np.int64)
           + bias[None, :].astype(np.int64))
    out = (acc * M[None, :] + (1 << (S[None, :] - 1))) >> S[None, :]
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out.reshape(oh, ow, oc).transpose(2, 0, 1)


def _pool(x: np.ndarray) -> np.ndarray:
    return np.maximum(np.maximum(x[:, 0::2, 0::2], x[:, 0::2, 1::2]),
                      np.maximum(x[:, 1::2, 0::2], x[:, 1::2, 1::2]))


def _fc(x: np.ndarray, w: np.ndarray, bias: np.ndarray,
        M: np.ndarray, S: np.ndarray, relu: bool) -> np.ndarray:
    v = x.reshape(-1).astype(np.int32)
    raw = w.astype(np.int32) @ v
    sx = int(v.sum(dtype=np.int32))
    acc = raw.astype(np.int64) - 128 * np.int64(sx) + bias.astype(np.int64)
    out = (acc * M + ((1 << (S - 1)))) >> S
    if relu:
        out = np.clip(out, 0, 255)
    return out


def infer(img: np.ndarray, model: dict) -> np.ndarray:
    """img: (28,28) uint8 -> 10 int32 logits."""
    g = GEOM
    L = model["layers"]
    x = img.reshape(1, 28, 28).astype(np.uint8)
    x = _conv(x, L["conv1"]["w"], L["conv1"]["bias"], L["conv1"]["M"],
              L["conv1"]["S"], g["conv1"]["OC"], g["conv1"]["K"])
    x = _pool(x)
    x = _conv(x, L["conv2"]["w"], L["conv2"]["bias"], L["conv2"]["M"],
              L["conv2"]["S"], g["conv2"]["OC"], g["conv2"]["K"])
    x = _pool(x)
    x = _fc(x, L["fc1"]["w"], L["fc1"]["bias"], L["fc1"]["M"],
            L["fc1"]["S"], relu=True)
    logits = _fc(x, L["fc2"]["w"], L["fc2"]["bias"], L["fc2"]["M"],
                 L["fc2"]["S"], relu=False)
    return logits.astype(np.int32)


def model_files(model_dir: str):
    """Sections to download to the FPGA: (sel, addr, bytes) chunks' source."""
    with open(os.path.join(model_dir, "metadata.json"), encoding="utf-8") as f:
        meta = json.load(f)
    return meta["sections"]
