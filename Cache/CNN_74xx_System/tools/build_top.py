"""Build the root sheet of the 12-board (Option A) hierarchy.

Every board is a group of sheet symbols inside one outlined box; the board's
backplane connector sheet is part of the same box.  Global labels still carry
every inter-board net, so the hierarchy root has no sheet pins.

The top is also the review index: a board table at the bottom lists the sheets,
external-net count and header count of each board, and the connection matrix is
written to output/connection_matrix.csv and docs/CONNECTION_MATRIX.md.

Run after the module, variant and board-connector builders:
    python tools/build_top.py
"""
from __future__ import annotations

import csv
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from build_boards import BOARDS, board_label
from kicad_gen import (RootSchematic, default_registry, write_project,
                       write_sym_lib_table)
from kicad_sexpr import atoms, children, first, parse

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(HERE, ".."))
PROJECT = "CNN_74xx_System"
ROOT_FILE = os.path.join(PROJECT_DIR, f"{PROJECT}.kicad_sch")
MANIFEST = os.path.join(PROJECT_DIR, "output", "boards", "BOARD_MANIFEST.csv")
CSV_FILE = os.path.join(PROJECT_DIR, "output", "connection_matrix.csv")
MD_FILE = os.path.join(PROJECT_DIR, "docs", "CONNECTION_MATRIX.md")

# Per-sheet one-line description for the hierarchy boxes.
SHEET_DESC = {
    "S01_Supervisor.kicad_sch":
        "Supervisor FSM, 2x 27C512 microcode, 74HCT273 state, watchdog",
    "S02_Timing.kicad_sch":
        "SETUP/WAIT/CAPTURE/HOLD/RELEASE, MEM_nCE/nOE/nWE, ACK handshake",
    "S04_Memories.kicad_sch":
        "7x 6264 SRAM, 12x 28C256 params, 8x 27C512 LUT/map, per-engine buffers",
    "S05_Pool1.kicad_sch":
        "POOL1 max-pool 12x12x8 -> 6x6x8, POOL_SEL tied 0",
    "S05_Pool2.kicad_sch":
        "POOL2 max-pool 10x10x16 -> 5x5x16, POOL_SEL tied 1",
    "S06_Argmax.kicad_sch":
        "10-way signed-32 argmax, result latch, ARGMAX_START/DONE",
    "S07_Conv1.kicad_sch":
        "CONV1 5x5x1 x 8 filters, 32-bit ACC, C1 memory interface",
    "S08_Conv2.kicad_sch":
        "CONV2 3x3x8 x 16 filters, 32-bit ACC, C2 memory interface",
    "S09_FC1.kicad_sch":
        "FC1 400->32 engine, FC_SEL tied 0, FC1_ACC/REQ to S17_FC1",
    "S09_FC2.kicad_sch":
        "FC2 32->10 engine, FC_SEL tied 1, FC2_ACC/REQ to S17_FC2",
    "S10_Top_IO.kicad_sch":
        "Host connector, clock/reset, image and weight load ports, LEDs",
    "S11_BusFabric.kicad_sch":
        "Master/region encode, 27C512 map ROM, ADDR tag, REQ/WE merge",
    "S11A_EngineMerge.kicad_sch":
        "FC1/FC2 and POOL1/POOL2 mux into the single S11 slots",
    "S12A_PoolLatch1.kicad_sch":
        "POOL1 input byte buffer DATA[7:0] -> IN_DATA1[7:0]",
    "S12A_PoolLatch2.kicad_sch":
        "POOL2 input byte buffer DATA[7:0] -> IN_DATA2[7:0]",
    "S12B_ScoreLatch.kicad_sch":
        "Argmax 4x 74HCT574 score staging + 74HC238 byte-lane decode",
    "S13_Requant_C1.kicad_sch":
        "CONV1 requant ACC>>8, ReLU/uint8 clamp (on-board with S07)",
    "S15_Requant_C2.kicad_sch":
        "CONV2 requant ACC>>9, ReLU/uint8 clamp (on-board with S08)",
    "S17_FC1.kicad_sch":
        "FC1 requant ACC>>8 uint8 (on-board with S09_FC1)",
    "S17_FC2.kicad_sch":
        "FC2 raw signed32, four-byte LE QSTB timing (on-board with S09_FC2)",
}

FLOW = ("IMAGE -> CONV1 -> POOL1 -> CONV2 -> POOL2 -> FC1 -> FC2 -> ARGMAX -> RESULT\n"
        "Board path: B12 -> B04 -> B05 -> B06 -> B07 -> B08 -> B09 -> B10 -> B12")


def load_manifest() -> dict[str, dict[str, str]]:
    if not os.path.exists(MANIFEST):
        print("ERROR: run tools/build_boards.py first (missing manifest)")
        sys.exit(1)
    with open(MANIFEST, encoding="utf-8-sig", newline="") as f:
        return {row["board"]: row for row in csv.DictReader(f)}


def flat_sheets():
    """[(sheet name, filename, page, desc, board id)] in board order."""
    out = []
    page = 2
    for bid, name, func, sheets, stage in BOARDS:
        for filename in sheets:
            short = os.path.splitext(filename)[0]
            out.append((f"B{bid}_{short}", filename, page,
                        SHEET_DESC.get(filename, func), bid))
            page += 1
        conn_file = f"{board_label(bid)}.kicad_sch"
        out.append((f"B{bid}_Conn", conn_file, page,
                    f"{name} backplane connector (2x20P, fixed power pinout)",
                    bid))
        page += 1
    return out


def _read_existing_uuids(path: str):
    """Reuse the root/sheet UUIDs from an existing root, if present."""
    if not os.path.exists(path):
        return None, {}
    with open(path, encoding="utf-8") as f:
        tree = parse(f.read())
    root = tree[0] if tree else []
    root_uuid = None
    u = first(root, "uuid")
    if u is not None and atoms(u):
        root_uuid = atoms(u)[0]
    sheet_uuids = {}
    for sh in children(root, "sheet"):
        un = first(sh, "uuid")
        file_name = None
        for prop in children(sh, "property"):
            a = atoms(prop)
            if len(a) >= 2 and a[0] == "Sheetfile":
                file_name = a[1]
                break
        if un is not None and file_name and atoms(un):
            sheet_uuids[file_name] = atoms(un)[0]
    return root_uuid, sheet_uuids


def collect_sheet_nets(sheets) -> dict[str, set[str]]:
    nets: dict[str, set[str]] = {}
    for _name, filename, _page, _desc, _bid in sheets:
        with open(os.path.join(PROJECT_DIR, filename), encoding="utf-8") as f:
            text = f.read()
        for net in set(re.findall(r'\(global_label\s+"([^"]+)"', text)):
            nets.setdefault(net, set()).add(filename)
    return nets


def write_connection_matrix(sheets, net_boards: dict[str, set[str]]) -> None:
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    external = {n: bs for n, bs in net_boards.items() if len(bs) >= 2}
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Net", "Boards", "BoardCount"])
        for net in sorted(external, key=lambda n: (n.lower(), n)):
            bs = sorted(external[net])
            w.writerow([net, ";".join(f"B{b}" for b in bs), len(bs)])

    today = datetime.date.today().isoformat()
    by_board: dict[str, list[str]] = {}
    for net, bs in external.items():
        for b in bs:
            by_board.setdefault(b, []).append(net)

    names = {bid: name for bid, name, _f, _s, _st in BOARDS}
    lines = [
        "# 板卡连接矩阵（12 板卡方案 A）",
        "",
        f"生成日期：{today}",
        "",
        "本矩阵按板卡统计 `global_label` 共现：一个网络只要出现在两块以上板卡的"
        "图页中，就必须经过底板。板内网络（ACC/REQ 对、IN_DATA 字节总线、"
        "SCORE_DATA）不会出现在这里。逐引脚定义见 "
        "`output/backplane/backplane_pinout.csv`。",
        "",
        "| 板卡 | 名称 | 对外网络数 |",
        "|---|---|---|",
    ]
    for bid, name, _f, _s, _st in BOARDS:
        lines.append(f"| B{bid} | {name} | {len(by_board.get(bid, []))} |")
    lines.append("")

    for bid, name, func, sheets, stage in BOARDS:
        nets = sorted(by_board.get(bid, []), key=lambda n: (n.lower(), n))
        lines.extend([
            f"## B{bid} {name}",
            "",
            f"功能：{func}",
            "",
            f"图页：{', '.join(sheets)}",
            "",
            f"阶段：{stage}",
            "",
        ])
        if not nets:
            lines.extend(["该板没有对外网络。", ""])
            continue
        lines.extend(["| 网络 | 对端板卡 |", "|---|---|"])
        for net in nets:
            peers = [f"B{b} {names.get(b, '')}"
                     for b in sorted(external[net]) if b != bid]
            lines.append(f"| `{net}` | {', '.join(peers)} |")
        lines.append("")

    lines.extend([
        "## 说明",
        "",
        "- `FC_SEL`/`POOL_SEL` 只从 B01 送 B11（map ROM 选择窗口），不再进引擎板。",
        "- `FC1_*` 只出现在 B08+B11/B03；`FC2_*` 只出现在 B09+B11/B03。",
        "- `POOL1_*` 只出现在 B05+B11/B03；`POOL2_*` 只出现在 B07+B11/B03。",
        "- B11 内部产生 `FC_*`/`POOL_*` 合并槽位，故它们不出现在底板清单中。",
        "",
    ])
    with open(MD_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"wrote {CSV_FILE}: {len(external)} inter-board nets")
    print(f"wrote {MD_FILE}")


def main() -> int:
    manifest = load_manifest()
    sheets = flat_sheets()
    missing = [f for _n, f, _p, _d, _b in sheets
               if not os.path.exists(os.path.join(PROJECT_DIR, f))]
    if missing:
        print("missing sheets:")
        for f in missing:
            print("  ", f)
        return 1

    existing_root_uuid, existing_sheet_uuids = _read_existing_uuids(ROOT_FILE)
    reg = default_registry()
    root = RootSchematic(
        reg, project=PROJECT, instance_path="/__ROOT_UUID__",
        title="74-Series 28x28 MNIST CNN - 12-Board Backplane System",
        paper="A0", rev="2.0", sheet_uuid=existing_root_uuid,
    )
    root.add_text(
        "74-Series 28x28 MNIST CNN - 12-Board Backplane System (Option A)",
        25, 14, size=4.2, justify="left top", bold=True,
    )
    root.add_text(
        "Twelve concrete boards, one 2x20P backplane connector group per board. "
        "Every inter-board net is a global label; the passive backplane only wires "
        "slot pins together.\n" + FLOW,
        25, 24, size=1.6, justify="left top",
    )

    # 4 columns x 3 rows of board boxes.
    col_x = [25.0, 305.0, 585.0, 865.0]
    row_y = [70.0, 258.0, 446.0]
    BOX_W, BOX_H = 272.0, 178.0
    SHEET_W, SHEET_H, PITCH = 120.0, 36.0, 50.0

    by_board: dict[str, list] = {}
    for item in sheets:
        by_board.setdefault(item[4], []).append(item)

    for idx, (bid, name, func, _mods, stage) in enumerate(BOARDS):
        x = col_x[idx % 4]
        y = row_y[idx // 4]
        for x1, y1, x2, y2 in ((x, y, x + BOX_W, y),
                               (x + BOX_W, y, x + BOX_W, y + BOX_H),
                               (x + BOX_W, y + BOX_H, x, y + BOX_H),
                               (x, y + BOX_H, x, y)):
            root.add_line(x1, y1, x2, y2, width=0.35)
        root.add_text(f"B{bid}  {name}", x + 4, y + 3, size=2.2,
                      justify="left top", bold=True)
        root.add_text(f"{func}\n{stage}", x + 4, y + 9, size=1.05,
                      justify="left top")
        row = manifest[f"B{bid}"]
        root.add_text(
            f"{row['external_nets']} external nets\n"
            f"{row['headers']} x 2x20P ({row['signal_pins']} pins)",
            x + 134, y + 8, size=1.0, justify="left top",
        )
        for k, (_n, filename, page, desc, _b) in enumerate(by_board[bid]):
            sy = y + 22 + k * PITCH
            short = os.path.splitext(filename)[0]
            sheet_name = (f"B{bid}_Conn" if short.endswith("_Conn")
                          else f"B{bid}_{short}")
            root.add_sheet(sheet_name, filename, x + 4, sy, SHEET_W, SHEET_H,
                           page=page,
                           sheet_uuid=existing_sheet_uuids.get(filename))
            root.add_text(desc, x + 130, sy + 2, size=0.9, justify="left top")

    # ------------------------------------------------------------ board table
    root.add_text("Board table (sheets, backplane budget)", 25, 632,
                  size=1.4, justify="left top", bold=True)
    table_rows = [["Board", "Slot", "Function", "Sheet files",
                   "Ext. nets", "Headers"]]
    for bid, name, func, mods, _stage in BOARDS:
        row = manifest[f"B{bid}"]
        table_rows.append([f"B{bid}", name, func, ", ".join(mods),
                           row["external_nets"], row["headers"]])
    root.add_table(
        25.0, 640.0, [38.0, 66.0, 300.0, 430.0, 50.0, 50.0],
        [7.0] + [9.0] * len(BOARDS), table_rows,
        font_size=0.85, header_font_size=0.95, header_rows=1,
        padding=0.8, outer_width=0.3, inner_width=0.15,
    )

    note_y = 640.0 + 7.0 + 9.0 * len(BOARDS) + 6.0
    root.add_text(
        "Backplane is passive: pins 1-4 +5V, 5-8 +3V3 (reserved), 9-14 GND, "
        "15-40 signals on every header.\n"
        "Per-board pinout: output/backplane/ ; board manifest: "
        "output/boards/BOARD_MANIFEST.csv ; net matrix: "
        "output/boards/backplane_nets.csv.\n"
        "Internal board nets: C1/C2/FC1/FC2 ACC+REQ pairs, IN_DATA1/2 byte "
        "buses and SCORE_DATA[31:0] never reach the backplane.",
        25, note_y, size=1.0, justify="left top",
    )

    for i, (net, x) in enumerate((("+5V", 25.0), ("+3V3", 105.0),
                                  ("GND", 185.0))):
        root.add_symbol("power:PWR_FLAG", f"FLG{i+1}", net, x, 800.0,
                        description=f"Hierarchy power flag {net}")
        root.add_wire(x, 800.0, x + 12.7, 800.0)
        root.add_global_label(net, x + 12.7, 800.0, 0)

    root.write(ROOT_FILE)
    write_project(os.path.join(PROJECT_DIR, f"{PROJECT}.kicad_pro"), PROJECT)
    write_sym_lib_table(os.path.join(PROJECT_DIR, "sym-lib-table"))

    # Patch the placeholder with the real root UUID and give every child symbol
    # the full hierarchical path /<root_uuid>/<sheet_uuid>.
    root_uuid = root.uuid
    with open(ROOT_FILE, encoding="utf-8") as f:
        root_txt = f.read()
    root_new = root_txt.replace("__ROOT_UUID__", root_uuid)
    if root_new != root_txt:
        with open(ROOT_FILE, "w", encoding="utf-8", newline="\n") as f:
            f.write(root_new)
    sheet_uuid = {sub["file"]: sub["uuid"] for sub in root.subsheets}
    for _name, filename, _page, _desc, _bid in sheets:
        path = os.path.join(PROJECT_DIR, filename)
        with open(path, encoding="utf-8") as f:
            txt = f.read()
        new_txt = txt.replace("__ROOT_UUID__", root_uuid)
        su = sheet_uuid[filename]
        new_txt = re.sub(
            r'\(path "/[0-9a-fA-F-]{36}(?:/[0-9a-fA-F-]{36})?"',
            f'(path "/{root_uuid}/{su}"', new_txt)
        if new_txt != txt:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_txt)

    # ------------------------------------------------------ connection matrix
    net_files = collect_sheet_nets(sheets)
    file_board = {f: b for _n, f, _p, _d, b in sheets}
    net_boards: dict[str, set[str]] = {}
    for net, files in net_files.items():
        net_boards[net] = {file_board[f] for f in files}
    write_connection_matrix(sheets, net_boards)

    print("wrote", ROOT_FILE, "root_uuid", root_uuid)
    print(f"  {len(sheets)} sheets in {len(BOARDS)} board groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
