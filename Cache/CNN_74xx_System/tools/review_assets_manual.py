"""Manual (non-Graphviz) review diagrams with larger labels."""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "output", "review_doc", "assets"))
FONT = "Microsoft YaHei"
plt.rcParams["font.sans-serif"] = [FONT, "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _canvas(w: float, h: float):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def _box(ax, x, y, w, h, title, sub="", fc="#FFFFFF", ec="#475569", fs=9.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.06",
                 facecolor=fc, edgecolor=ec, linewidth=1.0, zorder=3))
    if sub:
        ax.text(x + w / 2, y + h * 0.63, title, ha="center", va="center",
                fontsize=fs, color="#0F172A", zorder=4)
        ax.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center",
                fontsize=fs - 1.7, color="#334155", zorder=4)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                fontsize=fs, color="#0F172A", zorder=4)


def _arrow(ax, p1, p2, color="#475569", ls="-", rad=0.0, both=False,
           lw=1.2, label="", lpos=0.5, lcolor=None, lsize=7.0, dx=0, dy=0.1):
    style = "<|-|>" if both else "-|>"
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style,
                 mutation_scale=9, linewidth=lw, color=color,
                 linestyle=ls, connectionstyle=f"arc3,rad={rad}",
                 shrinkA=2, shrinkB=2, zorder=2))
    if label:
        x = p1[0] + (p2[0] - p1[0]) * lpos + dx
        y = p1[1] + (p2[1] - p1[1]) * lpos + dy
        ax.text(x, y, label, ha="center", va="bottom",
                fontsize=lsize, color=lcolor or color, zorder=6)


def _save(fig, name: str) -> None:
    fig.tight_layout(pad=0.1)
    p = os.path.join(OUT, name + ".png")
    fig.savefig(p, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


def dataflow_manual() -> None:
    fig, ax = _canvas(11.5, 3.6)
    y1, y2 = 2.25, 0.55
    w, h = 2.0, 1.0
    xs = [0.2, 2.45, 4.7, 6.95, 9.2]
    row1 = [
        ("INPUT", "28×28×1\n784 B", "#E0F2FE"),
        ("CONV1", "24×24×8\nS13 >>8", "#EDE9FE"),
        ("POOL1", "12×12×8\n288 B", "#FFEDD5"),
        ("CONV2", "10×10×16\nS15 >>9", "#EDE9FE"),
        ("POOL2", "5×5×16\n400 B", "#FFEDD5"),
    ]
    row2 = [
        ("FC1", "32 B\nS17 >>8", "#EDE9FE"),
        ("FC2", "10×4 B\nS17 raw", "#EDE9FE"),
        ("ARGMAX", "10 类", "#FEF3C7"),
        ("RESULT", "class 0..9", "#DCFCE7"),
    ]
    for x, (t, s, c) in zip(xs, row1):
        _box(ax, x, y1, w, h, t, s, c)
    for x, (t, s, c) in zip(xs[:4], row2):
        _box(ax, x, y2, w, h, t, s, c)
    for x in xs[:4]:
        _arrow(ax, (x + w, y1 + h / 2), (x + w + 0.25, y1 + h / 2))
    for x in xs[:3]:
        _arrow(ax, (x + w, y2 + h / 2), (x + w + 0.25, y2 + h / 2))
    ax.plot([10.2, 10.2, 1.2], [y1, 1.75, 1.75], color="#475569", lw=1.2, zorder=1)
    _arrow(ax, (1.2, 1.75), (1.2, y2 + h))
    ax.text(5.5, 1.82, "第 2 行继续", ha="center", va="bottom",
            fontsize=6.8, color="#64748B")
    _save(fig, "dataflow")


def engine_manual() -> None:
    fig, ax = _canvas(11.5, 5.2)
    w, h = 2.0, 1.0
    y1, y2 = 3.7, 1.7
    _box(ax, 0.2, y1, w, h, "S04 读数据", "IN / W / LUT", "#DCFCE7")
    _box(ax, 2.5, y1, w, h, "4× LUT lane", "8×8 → 16 位", "#E0F2FE")
    _box(ax, 4.8, y1, w, h, "4 级 A/B 流水", "8×74HCT574", "#E2E8F0")
    _box(ax, 7.1, y1, w, h, "加法树", "4 积 / 18 位", "#E2E8F0")
    _box(ax, 0.2, y2, w, h, "32 位 ACC", "8×283 + 4×574", "#EDE9FE")
    _box(ax, 2.5, y2, w, h, "V2 Requant", "S13/S15/S17", "#FCE7F3")
    _box(ax, 4.8, y2, w, h, "OUTHOLD", "574", "#E2E8F0")
    _box(ax, 7.1, y2, w, h, "写回 S04", "OUT 窗口", "#DCFCE7")
    for x in (0.2, 2.5, 4.8):
        _arrow(ax, (x + w, y1 + h / 2), (x + w + 0.25, y1 + h / 2))
        _arrow(ax, (x + w, y2 + h / 2), (x + w + 0.25, y2 + h / 2))
    ax.plot([8.1, 8.1, 1.2], [y1, 3.2, 3.2], color="#475569", lw=1.2, zorder=1)
    _arrow(ax, (1.2, 3.2), (1.2, y2 + h))
    _box(ax, 0.2, 0.35, 2.2, 0.8, "本地 FSM", "2×27C512", "#FEF3C7")
    _box(ax, 2.8, 0.35, 2.2, 0.8, "计数器链", "KX/KY/OX/OY/OC", "#FEF3C7")
    ax.text(5.4, 0.75, "控制：MAC_EN / 循环进位 / REQ_START / OUT_STB",
            ha="left", va="center", fontsize=7.0, color="#64748B")
    _arrow(ax, (1.3, 1.15), (1.2, 1.7), ls=":", lw=0.9)
    _arrow(ax, (3.9, 1.15), (3.5, 1.7), ls=":", lw=0.9)
    _save(fig, "engine")


def requant_manual() -> None:
    fig, ax = _canvas(11.2, 3.8)
    h = 0.95
    y1, y2 = 2.2, 0.55
    _box(ax, 0.2, y1, 1.5, h, "ACC", "32 位", "#EDE9FE")
    _box(ax, 2.0, y1, 1.8, h, "QRAW", "ACC[S+i]", "#E0F2FE")
    _box(ax, 4.1, y1, 1.6, h, "MUX 255", "SAT_POS", "#E2E8F0")
    _box(ax, 5.9, y1, 1.6, h, "MUX 0", "ACC31=1", "#E2E8F0")
    _box(ax, 7.7, y1, 1.6, h, "74HCT574", "Q[7:0]", "#FCE7F3")
    _box(ax, 9.5, y1, 1.4, h, "Q 输出", "", "#DCFCE7")
    _box(ax, 2.0, y2, 1.8, h, "HIGH OR", "ACC[S+8..31]", "#FEF3C7")
    _box(ax, 4.1, y2, 1.6, h, "SAT_POS", "HIGH & ~ACC31", "#FEF3C7")
    _box(ax, 6.2, y2, 1.2, h, "START", "", "#DCFCE7")
    _box(ax, 7.7, y2, 1.4, h, "QSTB", "74HC74", "#FEF3C7")
    _box(ax, 9.3, y2, 1.4, h, "DONE", "74HC74", "#FEF3C7")
    _arrow(ax, (1.7, y1 + h / 2), (2.0, y1 + h / 2))
    _arrow(ax, (3.8, y1 + h / 2), (4.1, y1 + h / 2))
    _arrow(ax, (5.7, y1 + h / 2), (5.9, y1 + h / 2))
    _arrow(ax, (7.5, y1 + h / 2), (7.7, y1 + h / 2))
    _arrow(ax, (9.3, y1 + h / 2), (9.5, y1 + h / 2))
    _arrow(ax, (0.95, y1), (2.9, y2 + h), ls=":", lw=0.9, rad=-0.18)
    _arrow(ax, (3.8, y2 + h / 2), (4.1, y2 + h / 2), ls=":")
    _arrow(ax, (4.9, y2 + h), (4.9, y1), ls=":", lw=0.9)
    _arrow(ax, (7.4, y2 + h / 2), (7.7, y2 + h / 2))
    _arrow(ax, (9.1, y2 + h / 2), (9.3, y2 + h / 2))
    ax.plot([0.95, 0.95, 6.7, 6.7], [y1 + h, 3.45, 3.45, y1 + h],
            color="#64748B", lw=0.9, zorder=1)
    _arrow(ax, (6.7, 3.45), (6.7, y1 + h))
    ax.text(3.8, 3.5, "ACC31", fontsize=6.5, color="#64748B")
    ax.plot([7.0, 7.0, 8.4], [y2 + h, 1.55, 1.55], color="#475569", lw=1.0, zorder=1)
    _arrow(ax, (8.4, 1.55), (8.4, y1))
    ax.text(8.5, 1.6, "load", fontsize=6.3, color="#64748B")
    _save(fig, "requant")


def supervisor_manual() -> None:
    fig, ax = _canvas(11.8, 4.4)
    _box(ax, 0.2, 3.1, 1.8, 0.8, "S10", "START/READY", "#E0F2FE")
    _box(ax, 2.4, 2.9, 2.4, 1.0, "2×27C512", "64K×16 微码", "#FEF3C7")
    _box(ax, 5.2, 3.1, 2.0, 0.8, "74HCT273", "状态寄存器", "#FEF3C7")
    _box(ax, 5.2, 1.7, 2.0, 0.8, "2×74HCT574", "输出寄存器", "#FEF3C7")
    _box(ax, 7.8, 1.7, 2.0, 0.8, "74HC238", "STAGE 译码", "#DCFCE7")
    _box(ax, 10.0, 1.7, 1.6, 0.8, "引擎", "START 脉冲", "#EDE9FE")
    _box(ax, 7.8, 3.1, 2.2, 0.8, "主机", "BUSY/DONE/ERROR", "#E0F2FE")
    _box(ax, 7.8, 0.3, 2.2, 0.8, "24 位超时", "TIMEOUT_CLR", "#FEF3C7")
    _box(ax, 2.4, 1.5, 2.4, 0.8, "各阶段 DONE", "TIMEOUT", "#FFEDD5")
    _arrow(ax, (2.0, 3.5), (2.4, 3.4), label="状态+条件", dx=0.0, dy=0.12, lsize=6.5)
    _arrow(ax, (4.8, 3.6), (5.2, 3.5), label="next", dy=0.12, lsize=6.5)
    _arrow(ax, (5.2, 3.3), (4.8, 3.2), label="当前状态", dy=-0.28, lsize=6.5)
    _arrow(ax, (4.8, 3.0), (5.2, 2.1), label="控制位", dx=0.25, dy=0.0, lsize=6.5)
    _arrow(ax, (7.2, 2.1), (7.8, 2.1))
    _arrow(ax, (9.8, 2.1), (10.0, 2.1))
    _arrow(ax, (7.2, 2.3), (7.8, 3.3), label="状态", dx=0.2, dy=0.0, lsize=6.5)
    _arrow(ax, (7.2, 1.9), (7.8, 0.9), label="TIMEOUT_CLR", dx=0.1, dy=0.0, lsize=6.0)
    ax.plot([3.6, 3.6, 2.4], [1.5, 1.1, 1.1], color="#475569", lw=1.0, zorder=1)
    _arrow(ax, (2.4, 1.1), (2.4, 2.9), ls=":", lw=1.0)
    ax.text(2.6, 1.15, "反馈", fontsize=6.3, color="#64748B")
    _save(fig, "supervisor")
