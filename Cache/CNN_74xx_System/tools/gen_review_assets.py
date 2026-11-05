"""Generate diagrams for the system review PDF (V2)."""
from __future__ import annotations

import os
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(PROJECT, "output", "review_doc", "assets")
os.makedirs(OUT, exist_ok=True)
DOT = r"C:\Program Files\Graphviz\bin\dot.exe"
FONT = "Microsoft YaHei"
plt.rcParams["font.sans-serif"] = [FONT, "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def dot(name: str, src: str) -> None:
    p = os.path.join(OUT, name + ".dot")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    png = os.path.join(OUT, name + ".png")
    subprocess.run([DOT, "-Tpng", "-Gdpi=180", p, "-o", png], check=True)
    print("wrote", png)


TOPO = r'''
digraph topo {
  graph [rankdir=LR, newrank=true, splines=polyline, nodesep=0.35,
         ranksep=0.65, fontname="Microsoft YaHei", fontsize=12,
         bgcolor="white", pad=0.15];
  node [shape=box, style="rounded,filled", fontname="Microsoft YaHei",
        fontsize=12, margin="0.14,0.08", penwidth=1.1];
  edge [fontname="Microsoft YaHei", fontsize=9, color="#64748B",
        arrowsize=0.65, penwidth=1.0];

  S10 [label="S10 主机接口\n8 MHz / 复位 / 加载 / 状态", fillcolor="#E0F2FE"];
  subgraph cluster_ctrl {
    label="调度与时序"; fontsize=11; color="#CBD5E1"; style="rounded,dashed";
    S01 [label="S01 监督 FSM\n20 状态 / 2×27C512", fillcolor="#FEF3C7"];
    S02 [label="S02 存储时序\nREQ/ACK/DONE", fillcolor="#FEF3C7"];
  }
  subgraph cluster_mem {
    label="存储与总线"; fontsize=11; color="#CBD5E1"; style="rounded,dashed";
    S11 [label="S11 总线适配\n74HC148 + 27C512 map", fillcolor="#DCFCE7"];
    S04 [label="S04 存储阵列\n7×6264 / 12×28C256 / 8×27C512", fillcolor="#DCFCE7"];
  }
  subgraph cluster_comp {
    label="计算与数据装配"; fontsize=11; color="#CBD5E1"; style="rounded,dashed";
    S07 [label="S07 CONV1 引擎", fillcolor="#EDE9FE"];
    S13 [label="S13 V2 Requant\nACC>>8", fillcolor="#FCE7F3"];
    S08 [label="S08 CONV2 引擎", fillcolor="#EDE9FE"];
    S15 [label="S15 V2 Requant\nACC>>9", fillcolor="#FCE7F3"];
    S09 [label="S09 FC1/FC2 引擎", fillcolor="#EDE9FE"];
    S17 [label="S17 FC Requant\nFC1>>8 / FC2 raw", fillcolor="#FCE7F3"];
    S05 [label="S05 POOL1/2\n2×2 max", fillcolor="#FFEDD5"];
    S06 [label="S06 ARGMAX\n10 类 signed32", fillcolor="#FFEDD5"];
    S12 [label="S12 数据装配\n541 + 4×574", fillcolor="#E2E8F0"];
  }

  S10 -> S01 [label="START / READY"];
  S10 -> S04 [label="LOAD_ADDR/DATA", style=dashed];
  S01 -> S07 [label="C1_START", style=dotted];
  S01 -> S05 [label="P1/P2_START", style=dotted];
  S01 -> S08 [label="C2_START", style=dotted];
  S01 -> S09 [label="FC1/FC2_START", style=dotted];
  S01 -> S06 [label="ARGMAX_START", style=dotted];

  S07 -> S13 [label="ACC / START"];
  S13 -> S07 [label="Q / QSTB / DONE", style=dashed];
  S08 -> S15 [label="ACC / START"];
  S15 -> S08 [label="Q / QSTB / DONE", style=dashed];
  S09 -> S17 [label="ACC / START"];
  S17 -> S09 [label="Q / QSTB / DONE", style=dashed];

  S07 -> S11 [label="ADDR/REQ/WE"];
  S08 -> S11 [label="ADDR/REQ/WE"];
  S09 -> S11 [label="ADDR/REQ/WE"];
  S11 -> S04 [label="ADDR / MEM_SEL"];
  S04 -> S11 [label="DATA", style=dashed];
  S11 -> S02 [label="REQ / WE"];
  S02 -> S04 [label="nCE/nOE/nWE"];
  S02 -> S07 [label="ACK/DONE", style=dotted];
  S02 -> S08 [label="ACK/DONE", style=dotted];
  S02 -> S09 [label="ACK/DONE", style=dotted];

  S12 -> S05 [label="IN_DATA"];
  S06 -> S12 [label="SCORE_DATA"];
  S06 -> S01 [label="ARGMAX_DONE", style=dotted];
  S05 -> S04 [label="OUT_* 未连接", color="#DC2626", fontcolor="#DC2626", style=dashed];
  S05 -> S01 [label="P1/P2_DONE", style=dotted];
}
'''

DATAFLOW = r'''
digraph flow {
  graph [rankdir=LR, nodesep=0.35, ranksep=0.45, fontname="Microsoft YaHei",
         fontsize=12, bgcolor="white", pad=0.15];
  node [shape=box, style="rounded,filled", fontname="Microsoft YaHei",
        fontsize=12, margin="0.14,0.08", penwidth=1.1];
  edge [fontname="Microsoft YaHei", fontsize=9, color="#64748B", arrowsize=0.65];

  IN  [label="INPUT
28×28×1
784 B", fillcolor="#E0F2FE"];
  C1  [label="CONV1
24×24×8
4608 B
S13: ACC>>8", fillcolor="#EDE9FE"];
  P1  [label="POOL1
12×12×8
288 B", fillcolor="#FFEDD5"];
  C2  [label="CONV2
10×10×16
1600 B
S15: ACC>>9", fillcolor="#EDE9FE"];
  P2  [label="POOL2
5×5×16
400 B", fillcolor="#FFEDD5"];
  F1  [label="FC1
32 B
S17: ACC>>8", fillcolor="#EDE9FE"];
  F2  [label="FC2
10×4 B
S17: raw s32", fillcolor="#EDE9FE"];
  AM  [label="ARGMAX
class 0..9", fillcolor="#FEF3C7"];
  R   [label="RESULT
4-bit", fillcolor="#DCFCE7"];

  IN -> C1 -> P1 -> C2 -> P2 -> F1 -> F2 -> AM -> R;
}
'''


ENGINE = r'''
digraph eng {
  graph [rankdir=LR, nodesep=0.35, ranksep=0.42, fontname="Microsoft YaHei",
         fontsize=12, bgcolor="white", pad=0.12];
  node [shape=box, style="rounded,filled", fontname="Microsoft YaHei",
        fontsize=11, margin="0.12,0.07", penwidth=1.1];
  edge [fontname="Microsoft YaHei", fontsize=9, color="#64748B", arrowsize=0.65];

  SRC [label="S04 读数据\nIN / W / LUT", fillcolor="#DCFCE7"];
  LUT [label="4× LUT lane\n8×8 → 16 位", fillcolor="#E0F2FE"];
  PIPE [label="4 级 A/B 流水\n8×74HCT574", fillcolor="#E2E8F0"];
  ADD  [label="4 积加法树\n18 位 / 74HC283", fillcolor="#E2E8F0"];
  ACC  [label="32 位 ACC\n8×74HC283 + 4×574", fillcolor="#EDE9FE"];
  RQ   [label="S13/S15/S17\nV2 Requant", fillcolor="#FCE7F3"];
  HOLD [label="OUTHOLD\n574", fillcolor="#E2E8F0"];
  WR   [label="写回 S04\nOUT 窗口", fillcolor="#DCFCE7"];
  FSM  [label="本地 FSM\n2×27C512", fillcolor="#FEF3C7"];
  CNT  [label="KX/KY/OX/OY/OC\n74HC161 链", fillcolor="#FEF3C7"];

  SRC -> LUT -> PIPE -> ADD -> ACC -> RQ -> HOLD -> WR;
  FSM -> CNT [label="MAC_EN / loop"];
  CNT -> SRC [label="ADDR", style=dashed];
  FSM -> PIPE [label="LUT_*_LATCH", style=dotted];
  FSM -> ACC [label="ACC_CLR", style=dotted];
  FSM -> RQ [label="REQ_START", style=dotted];
  RQ -> FSM [label="REQ_DONE", style=dotted];
}
'''

REQ = r'''
digraph rq {
  graph [rankdir=LR, nodesep=0.35, ranksep=0.45, fontname="Microsoft YaHei",
         fontsize=11, bgcolor="white", pad=0.12];
  node [shape=box, style="rounded,filled", fontname="Microsoft YaHei",
        fontsize=11, margin="0.12,0.07", penwidth=1.1];
  edge [fontname="Microsoft YaHei", fontsize=9, color="#64748B", arrowsize=0.65];

  ACC [label="ACC[31:0]", fillcolor="#EDE9FE"];
  RAW [label="QRAW[i]\nACC[S+i] / ACC31", fillcolor="#E0F2FE"];
  M1  [label="MUX 255\nSAT_POS", fillcolor="#E2E8F0"];
  M2  [label="MUX 0\nACC31=1", fillcolor="#E2E8F0"];
  REG [label="74HCT574\nQ[7:0]", fillcolor="#FCE7F3"];
  HIGH [label="HIGH OR\nACC[S+8..31]", fillcolor="#FEF3C7"];
  SAT [label="SAT_POS\nHIGH & ~ACC31", fillcolor="#FEF3C7"];

  START [label="START", shape=oval, fillcolor="#DCFCE7"];
  D1 [label="74HC74\nQSTB", fillcolor="#FEF3C7"];
  D2 [label="74HC74\nDONE", fillcolor="#FEF3C7"];
  QOUT [label="Q[7:0]\n输出", shape=oval, fillcolor="#DCFCE7"];

  ACC -> RAW -> M1 -> M2 -> REG;
  ACC -> HIGH -> SAT -> M1 [style=dashed];
  ACC -> M2 [label="ACC31", style=dashed];
  START -> REG [label="load"];
  START -> D1 -> D2;
  REG -> QOUT [label="Q"];
}
'''

SUP = r'''
digraph sup {
  graph [rankdir=LR, nodesep=0.3, ranksep=0.45, fontname="Microsoft YaHei",
         fontsize=11, bgcolor="white", pad=0.12];
  node [shape=box, style="rounded,filled", fontname="Microsoft YaHei",
        fontsize=11, margin="0.12,0.07", penwidth=1.1];
  edge [fontname="Microsoft YaHei", fontsize=9, color="#64748B", arrowsize=0.65];

  IN [label="S10\nSTART / READY", fillcolor="#E0F2FE"];
  ROM [label="2×27C512\n64K×16 微码", fillcolor="#FEF3C7"];
  SR [label="74HCT273\n状态寄存器", fillcolor="#FEF3C7"];
  OR [label="2×74HCT574\n输出寄存器", fillcolor="#FEF3C7"];
  DEC [label="74HC238\nSTAGE_CODE 译码", fillcolor="#DCFCE7"];
  ENG [label="S07/S05/S08/S09/S06\nSTART 脉冲", fillcolor="#EDE9FE"];
  DONE [label="各阶段 DONE\nTIMEOUT", fillcolor="#FFEDD5"];
  HOST [label="BUSY / DONE / ERROR\nRESULT_VALID", fillcolor="#E0F2FE"];
  TMO [label="24 位超时\n计数器 CLR", fillcolor="#FEF3C7"];

  IN -> ROM [label="状态 + 条件"];
  ROM -> SR [label="next state"];
  ROM -> OR [label="控制位"];
  SR -> ROM [label="当前状态"];
  OR -> DEC -> ENG;
  OR -> HOST;
  DONE -> ROM [label="反馈", style=dashed];
  OR -> TMO [label="TIMEOUT_CLR", style=dotted];
}
'''


def topology_manual() -> None:
    """Clean three-plane topology figure (control / memory / compute)."""
    fig, ax = plt.subplots(figsize=(9.2, 6.6))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def plane(x, y, w, h, label, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.02,rounding_size=0.12",
                     facecolor=color, edgecolor="#CBD5E1", linewidth=1.0,
                     linestyle=(0, (4, 3)), zorder=0))
        ax.text(x + 0.12, y + h - 0.12, label, ha="left", va="top",
                fontsize=8.2, color="#475569", fontweight="bold", zorder=5)

    def box(x, y, w, h, title, sub="", fc="#FFFFFF", ec="#475569", fs=9.0):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.02,rounding_size=0.07",
                     facecolor=fc, edgecolor=ec, linewidth=1.0, zorder=3))
        if sub:
            ax.text(x + w / 2, y + h * 0.63, title, ha="center", va="center",
                    fontsize=fs, color="#0F172A", zorder=4)
            ax.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center",
                    fontsize=fs - 1.6, color="#334155", zorder=4)
        else:
            ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                    fontsize=fs, color="#0F172A", zorder=4)

    def arrow(p1, p2, color="#475569", ls="-", rad=0.0, both=False,
              lw=1.25, label="", lpos=0.5, lcolor=None, lsize=7.0, dx=0, dy=0.12):
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

    plane(0.15, 3.4, 3.75, 6.2, "控制平面", "#F8FAFC")
    plane(4.45, 4.6, 3.7, 5.0, "存储平面", "#F8FAFC")
    plane(8.95, 0.55, 6.75, 9.05, "计算与数据装配平面", "#F8FAFC")

    box(0.40, 8.55, 3.20, 0.80, "S10 主机接口", "8 MHz / 复位 / 加载 / 状态", "#E0F2FE")
    box(0.40, 6.95, 3.20, 0.90, "S01 监督 FSM", "20 状态 / 2×27C512 微码", "#FEF3C7")
    box(0.40, 5.35, 3.20, 0.90, "S02 存储时序", "REQ / ACK / DONE / WAIT", "#FEF3C7")
    ax.text(2.00, 4.55, "S01 只发阶段 START，\n不直接操作存储器", ha="center",
            va="center", fontsize=7.2, color="#64748B")

    box(4.70, 7.75, 3.20, 0.90, "S11 总线适配", "74HC148 + 27C512 map", "#DCFCE7")
    box(4.70, 6.00, 3.20, 1.00, "S04 存储阵列", "7×6264 / 12×28C256 / 8×27C512", "#DCFCE7")
    ax.text(6.30, 5.30, "8 KB / 32 KB / 64 KB 窗口\nMEM_SEL[4:0] 选择", ha="center",
            va="center", fontsize=7.2, color="#64748B")

    # Compute plane rows: engine + requant, pool/assembly, ...
    box(9.20, 8.35, 2.50, 0.75, "S07 CONV1", "4×LUT / 32-bit ACC", "#EDE9FE")
    box(12.20, 8.35, 3.20, 0.75, "S13 Requant C1", "ACC >> 8 → clamp u8", "#FCE7F3")
    box(9.20, 7.00, 2.50, 0.75, "S05 POOL1/2", "2×2 max / 42 DIP", "#FFEDD5")
    box(12.20, 7.00, 3.20, 0.75, "S12 数据装配", "541 + 4×574", "#E2E8F0")
    box(9.20, 5.65, 2.50, 0.75, "S08 CONV2", "4×LUT / 32-bit ACC", "#EDE9FE")
    box(12.20, 5.65, 3.20, 0.75, "S15 Requant C2", "ACC >> 9 → clamp u8", "#FCE7F3")
    box(9.20, 4.30, 2.50, 0.75, "S09 FC1/FC2", "4×LUT / 32-bit ACC", "#EDE9FE")
    box(12.20, 4.30, 3.20, 0.75, "S17 Requant FC", "FC1 >> 8 / FC2 raw s32", "#FCE7F3")
    box(9.20, 2.95, 2.50, 0.75, "S06 ARGMAX", "10 类 signed32", "#FFEDD5")
    box(12.20, 2.95, 3.20, 0.75, "RESULT", "class 0..9 / 4-bit", "#DCFCE7")
    ax.text(12.35, 1.55, "评审发现：S05 的 OUT_DATA / OUT_ADDR / OUT_WE\n"
            "与 IN_ADDR 只连到本页，未闭环到 S04（P0）",
            ha="left", va="center", fontsize=7.2, color="#DC2626")

    # Control rail
    ax.add_patch(FancyBboxPatch((8.55, 2.55), 0.28, 6.25,
                 boxstyle="round,pad=0.01,rounding_size=0.05",
                 facecolor="#FEF3C7", edgecolor="#D97706", linewidth=0.9, zorder=2))
    ax.text(8.69, 5.65, "阶段 START / DONE", rotation=90, ha="center",
            va="center", fontsize=6.8, color="#92400E", zorder=5)
    # Memory access rail
    ax.add_patch(FancyBboxPatch((8.05, 2.95), 0.22, 5.90,
                 boxstyle="round,pad=0.01,rounding_size=0.04",
                 facecolor="#DCFCE7", edgecolor="#059669", linewidth=0.9, zorder=2))
    ax.text(8.16, 5.60, "存储访问", rotation=90, ha="center",
            va="center", fontsize=6.8, color="#065F46", zorder=5)

    # Host and control
    arrow((2.00, 8.55), (2.00, 7.85), label="START / READY", dx=0.55)
    arrow((3.60, 8.92), (4.70, 8.30), ls=(0, (4, 2)), rad=-0.22,
          label="LOAD", lpos=0.45, dy=0.10, lsize=6.2)
    arrow((3.60, 7.40), (8.55, 7.40))

    # Control fan-out
    for y in (8.72, 7.37, 6.02, 4.67, 3.32):
        arrow((8.83, y), (9.20, y), lw=0.9)

    # Requant pairs
    arrow((11.70, 8.72), (12.20, 8.72), both=True, label="A/Q", dy=0.08, lsize=5.8)
    arrow((11.70, 6.02), (12.20, 6.02), both=True, label="A/Q", dy=0.08, lsize=5.8)
    arrow((11.70, 4.67), (12.20, 4.67), both=True, label="A/Q", dy=0.08, lsize=5.8)
    arrow((12.20, 7.37), (11.70, 7.37))
    arrow((11.70, 3.32), (12.20, 3.32))

    # Memory access fan-in to rail
    for y in (8.72, 6.02, 4.67, 3.32):
        arrow((9.20, y), (8.27, y), color="#059669", lw=0.9)
    arrow((8.05, 8.45), (7.90, 8.45), color="#059669", lw=1.2)
    arrow((6.30, 7.75), (6.30, 7.00), both=True, color="#059669")

    # S11 -> S02 -> S04
    arrow((4.70, 7.80), (3.60, 5.85), color="#D97706", rad=0.20)
    arrow((3.60, 5.90), (4.70, 6.50), color="#D97706", rad=-0.20)
    ax.text(3.62, 4.72, "S02 产生 nCE / nOE / nWE\n和 ACK / DONE", ha="left",
            va="center", fontsize=6.6, color="#92400E")

    # Known open path
    arrow((9.20, 7.00), (7.90, 6.55), color="#DC2626", ls=(0, (3, 2)),
          rad=0.12)

    ax.text(0.20, 0.22, "实线：地址 / 数据 / 控制    橙色：S02 存储时序    绿色：存储访问    红色：未闭环",
            ha="left", va="center", fontsize=6.6, color="#64748B")

    fig.tight_layout(pad=0.15)
    p = os.path.join(OUT, "topology.png")
    fig.savefig(p, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


def wave(name: str, title: str, signals: list[tuple[str, list[int]]]) -> None:
    n = len(signals[0][1])
    step = 2.0
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(signals) + 1.0))
    for k, (label, vals) in enumerate(signals):
        y = (len(signals) - 1 - k) * step
        ax.step(range(n + 1), [y + v for v in vals] + [y + vals[-1]], where="post",
                linewidth=1.8, color="#1d4ed8")
        ax.text(-0.2, y + 0.22, label, ha="right", va="bottom",
                fontsize=9, family=FONT)
        ax.axhline(y, color="#cbd5e1", linewidth=0.6, zorder=0)
        ax.axhline(y + 1, color="#eef2f7", linewidth=0.5, zorder=0)
    ax.set_xlim(-0.1, n + 0.1)
    ax.set_ylim(-0.5, step * len(signals) - 0.5)
    ax.set_yticks([])
    ax.set_xticks(range(n + 1))
    ax.set_xticklabels([str(i) for i in range(n + 1)], fontsize=8)
    ax.set_xlabel("CLK cycle", fontsize=9, family=FONT)
    ax.set_title(title, fontsize=11, family=FONT, loc="left")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#e2e8f0", linewidth=0.6)
    fig.tight_layout()
    p = os.path.join(OUT, name + ".png")
    fig.savefig(p, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


def memmap() -> None:
    rows = [
        ("SRAM 0..6", 0, 7, "#DBEAFE"),
        ("unused 7", 7, 1, "#F1F5F9"),
        ("W 8..11", 8, 4, "#DCFCE7"),
        ("B 12..15", 12, 4, "#FEF3C7"),
        ("Q 16..19", 16, 4, "#FCE7F3"),
        ("LUT 20..27", 20, 8, "#EDE9FE"),
        ("unused 28..31", 28, 4, "#F1F5F9"),
    ]
    fig, ax = plt.subplots(figsize=(11, 2.0))
    for label, start, width, color in rows:
        ax.broken_barh([(start, width)], (0.2, 0.6), facecolors=color,
                       edgecolors="#475569", linewidth=0.8)
        ax.text(start + width / 2, 0.5, label, ha="center", va="center",
                fontsize=9, family=FONT)
    ax.set_xlim(0, 32)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks(range(0, 33, 2))
    ax.set_xlabel("MEM_SEL[4:0]  (ADDR[20:16])", fontsize=9, family=FONT)
    ax.set_title("S04 memory windows (8 KB SRAM / 32 KB EEPROM / 64 KB LUT)",
                 fontsize=10, family=FONT, loc="left")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#e2e8f0", linewidth=0.6)
    fig.tight_layout()
    p = os.path.join(OUT, "memmap.png")
    fig.savefig(p, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote", p)


def main() -> None:
    topology_manual()
    from review_assets_manual import (dataflow_manual, engine_manual,
                                      requant_manual, supervisor_manual)
    dataflow_manual()
    engine_manual()
    requant_manual()
    supervisor_manual()
    wave("supervisor_wave", "Supervisor: one stage start/wait/finish", [
        ("CLK", [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]),
        ("START", [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        ("BUSY", [0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0]),
        ("C1_START", [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        ("C1_DONE", [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0]),
        ("DONE", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0]),
        ("RESULT_VALID", [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1]),
    ])
    wave("mem_read_wave", "S02 read transaction: WAIT_READ=3", [
        ("CLK", [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]),
        ("REQ", [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0]),
        ("nCE", [1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1]),
        ("nOE", [1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1]),
        ("ACK", [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
        ("DONE", [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]),
    ])
    wave("requant_wave", "V2 requant: START / QSTB / DONE", [
        ("CLK", [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]),
        ("START", [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]),
        ("QSTB", [0, 0, 1, 0, 0, 0, 0, 0, 0, 0]),
        ("DONE", [0, 0, 0, 1, 0, 0, 0, 0, 0, 0]),
        ("Q[7:0]", [0, 0, 1, 1, 0, 0, 0, 0, 0, 0]),
    ])
    memmap()


if __name__ == "__main__":
    main()
