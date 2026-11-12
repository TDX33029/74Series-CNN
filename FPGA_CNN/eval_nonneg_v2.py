"""方案 A：非负权重（0..255，ZP=0）在 V2 契约下的精度实测。

V2 契约（docs/REQUANT_SIMPLE_V2.md）：
    ZP_X = ZP_W = ZP_OUT = 0, bias = 0，
    每层一个 2^S：Q = clamp(ACC >> S, 0, 255)，FC2 输出原始 signed32。

本脚本按方案 A 的假设重新训练：
  - Conv/Linear 全部 bias=False（V2 没有 bias 加法器）
  - 每次 optimizer.step() 后把权重投影到 >= 0（非负约束）
然后按 V2 规则的整数推理（无符号乘法、整数累加、算术右移截断）评估精度。

用法：
    python eval_nonneg_v2.py [--epochs 12] [--limit 2000] [--calib 2000]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_export as T  # noqa: E402
from eval_v2_quant import im2col, pool2  # noqa: E402

DATA = os.path.join(os.path.dirname(HERE), "MNIST")
CKPT = os.path.join(HERE, "cnn28_nonneg.pt")


def build_nonneg_model():
    import torch.nn as nn

    return nn.Sequential(
        nn.Conv2d(1, 8, 5, bias=False), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(8, 16, 3, bias=False), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(400, 32, bias=False), nn.ReLU(),
        nn.Linear(32, 10, bias=False),
    )


def train_nonneg(xtr, ytr, xte, yte, epochs: int, batch: int, seed: int):
    import torch
    import torch.nn as nn
    import torch.optim as optim

    torch.manual_seed(seed)
    np.random.seed(seed)
    model = build_nonneg_model()
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
        t0 = time.time()
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            opt.zero_grad()
            out = model(xt[idx])
            loss = lossf(out, yt[idx])
            loss.backward()
            opt.step()
            # 方案 A：非负投影
            with torch.no_grad():
                for p in model.parameters():
                    p.clamp_(min=0.0)
            tot += loss.item() * len(idx)
        sched.step()
        model.eval()
        acc = 0
        with torch.no_grad():
            for i in range(0, len(xv), 1000):
                pred = model(xv[i:i + 1000]).argmax(1)
                acc += (pred == yv[i:i + 1000]).sum().item()
        print(f"epoch {ep:2d}/{epochs}  loss {tot / n:.4f}  test acc {acc / len(xv):.4f}"
              f"  ({time.time() - t0:.0f}s)", flush=True)
        torch.save(model.state_dict(), CKPT)
    return model


def calibrate_amax(model, xtr, limit=2000):
    """每层激活的最大绝对值（与 eval_v2_quant.py 的 V2 路径一致）。"""
    import torch

    hooks = {}
    acts = {}

    def mk(name):
        def hook(_m, _i, out):
            acts[name] = max(acts.get(name, 0.0), float(out.abs().max()))
        return hook

    m = model
    h = [m[0].register_forward_hook(mk("conv1")),
         m[3].register_forward_hook(mk("conv2")),
         m[7].register_forward_hook(mk("fc1"))]
    with torch.no_grad():
        for i in range(0, limit, 500):
            m(torch.from_numpy(xtr[i:i + 500]).float().unsqueeze(1) / 255.0)
    for x in h:
        x.remove()
    return acts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--calib", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--skip-train", action="store_true")
    args = ap.parse_args()

    import torch

    xtr, ytr, xte, yte = T.load_mnist(DATA)
    xte, yte = xte[:args.limit], yte[:args.limit]

    if args.skip_train and os.path.exists(CKPT):
        model = build_nonneg_model()
        model.load_state_dict(torch.load(CKPT, map_location="cpu"))
        model.eval()
    else:
        model = train_nonneg(xtr, ytr, xte, yte, args.epochs, args.batch, args.seed)

    with torch.no_grad():
        fl = model(torch.from_numpy(xte).float().unsqueeze(1) / 255.0).numpy()
    acc_float = float((fl.argmax(1) == yte).mean())

    sd = {k: v.detach().numpy() for k, v in model.state_dict().items()}
    acts = calibrate_amax(model, xtr[:args.calib])

    # 每层：非负对称量化 w/s_w，s_w = max(w)/255
    q, sh = {}, {}
    for nm, key, k in (("conv1", "0.weight", 5), ("conv2", "3.weight", 3),
                       ("fc1", "7.weight", 0), ("fc2", "9.weight", 0)):
        w = sd[key]
        s_w = max(float(w.max()), 1e-9) / 255.0
        qw = np.clip(np.round(w / s_w), 0, 255).astype(np.int32)
        q[nm], sh[nm] = qw, k

    # 逐层标定 S：acc 的最大值 / 255 取 2 的幂（与 build_requant_simple.py 同规则）
    a = xtr[:args.calib].astype(np.uint8)[:, None, :, :]
    S = {}
    for nm, k in (("conv1", 5), ("conv2", 3), ("fc1", 0), ("fc2", 0)):
        qw = q[nm]
        if k:
            pmat = im2col(a, k).astype(np.int32)
            acc = pmat @ qw.reshape(qw.shape[0], -1).astype(np.int32).T
            amax = float(np.abs(acc).max())
            S[nm] = max(1, int(np.floor(np.log2(amax / 255.0)))) if amax > 1 else 1
            out = np.clip(acc >> S[nm], 0, 255)
            oh = a.shape[2] - k + 1
            a = out.reshape(a.shape[0], oh, oh, qw.shape[0]).transpose(0, 3, 1, 2)
            a = pool2(a).astype(np.uint8)
        else:
            v = a.reshape(a.shape[0], -1).astype(np.int32)
            acc = v @ qw.astype(np.int32).T
            amax = float(np.abs(acc).max())
            if nm == "fc2":
                S[nm] = 0
            else:
                S[nm] = max(1, int(np.floor(np.log2(amax / 255.0)))) if amax > 1 else 1
                a = np.clip(acc >> S[nm], 0, 255).astype(np.uint8)
    print("layer shifts:", S, flush=True)

    def run_v2(xb):
        a = xb[:, None, :, :]
        for nm, k in (("conv1", 5), ("conv2", 3)):
            qw = q[nm]
            pmat = im2col(a, k).astype(np.int32)
            acc = pmat @ qw.reshape(qw.shape[0], -1).astype(np.int32).T
            out = np.clip(acc >> S[nm], 0, 255)
            oh = a.shape[2] - k + 1
            a = out.reshape(a.shape[0], oh, oh, qw.shape[0]).transpose(0, 3, 1, 2)
            a = pool2(a).astype(np.uint8)
        for nm in ("fc1", "fc2"):
            qw = q[nm]
            v = a.reshape(a.shape[0], -1).astype(np.int32)
            acc = v @ qw.astype(np.int32).T
            if nm == "fc1":
                a = np.clip(acc >> S[nm], 0, 255).astype(np.uint8)
            else:
                a = acc  # raw signed32
        return a

    # 整数推理（与板上完全相同的算法）
    pred = []
    for i in range(0, len(xte), 500):
        pred.append(run_v2(xte[i:i + 500].astype(np.uint8)))
    logits = np.concatenate(pred, axis=0)
    acc_v2 = float((logits.argmax(1) == yte).mean())

    print(f"\nfloat   : {acc_float:.4f}")
    print(f"V2 非负 : {acc_v2:.4f}   (limit={args.limit})")
    print(f"权重范围: conv1 max={q['conv1'].max()}  负值个数={int((q['conv1'] < 0).sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
