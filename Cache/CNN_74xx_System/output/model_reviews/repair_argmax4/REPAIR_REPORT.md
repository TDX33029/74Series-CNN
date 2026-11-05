# Argmax 四字节读事务闭环报告（S06/S04/S11/S12）

日期：2026-11-05  
主工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`  
目标：让 Argmax 每次读取一个 32 位 score 时，真正执行 4 次 S02 REQ/ACK 字节读；S06 输出 `{class,byte}` 地址，S04 提供 Argmax 地址通路，S12 在 `MEM_ACK` 锁存四个字节。

## 0. 结论

| 项目 | 结果 |
|---|---|
| S06 字节计数 | 新增 U39 74HC161（2 位），`BYTE0/BYTE1` |
| S06 地址 | U38 输出 `SCORE_ADDR[5:0]={CLASS,BYTE}` = `class*4+byte` |
| S06 握手 | `RD -> WT(wait MEM_ACK) -> BYDONE(wait MEM_DONE) -> BYNEXT`，每类 4 次 |
| S04 地址 | 新增 U50/U51 74HCT541，`ARGMAX_BUSY_N` 期间把 `SCORE_ADDR` 零扩展到 `ADDR[15:0]` |
| S11 主控 | Argmax 作为 master 4：74HC148 I3=`ARGMAX_BUSY_N`，S2=`MASTER2` 接 27C512 A7；全部 region 映射 `MEM_SEL=6`（FC2_LOGITS）；`REQ` 合并 `SCORE_RD` |
| S12 锁存 | 74HC238 E3 从 `SCORE_RD` 改为 `MEM_ACK`（S02 CAPTURE 数据有效） |
| 顶层 ERC | 0 errors / 836 warnings（`output/top-erc-final.rpt`） |
| 仿真 | `sim/run_all.py` **10/10**；`argmax_s12` 新检查 |
| 网表审计 | 3 单节点 / 21 未展开总线 / 1 DONE 驱动 |
| BOM | 953 件（527 片 IC + 15 个块符号） |

## 1. S06 FSM

状态：

```
IDLE -> INIT -> {RD -> WT -> BYDONE -> BYNEXT} x4
     -> (class 0) LD0 -> NEXT
     -> (class 1..9) CMP -> NEXT
     -> ... -> DONE -> WAIT -> IDLE
```

关键信号：

- `S_RD`/`S_WT`：`SCORE_RD = S_RD | S_WT`。
- `S_WT` 保持到 `MEM_ACK`；`D_WT = S_RD | (S_WT & ~MEM_ACK)`。
- `S_BYTE_DONE` 保持到 `MEM_DONE`；`D_BYTE_DONE = (S_WT & MEM_ACK) | (S_BYTE_DONE & ~MEM_DONE)`。
- `BYTE_INC = S_BYTE_DONE & MEM_DONE & ~BYTE3`；`BYTE3 = BYTE0 & BYTE1`。
- `BYTE_LAST = S_BYTE_DONE & MEM_DONE & BYTE3`。
- `BYTE_CLR = S_INIT | S_LD0 | S_NEXT`，经 U37d 与 `RESET_N` 合成 `BYTE_CLR_N`。
- `FIRST` DFF：INIT 置位，LD0 清零；决定第 4 个字节后走 `LD0`（class 0）还是 `CMP`。

新增器件（S06）：U39 74HC161、U40 74HC08、U42 74HC04、U45 74HC08、U46 74HC32、U47 74HC04、U48 74HC08。

## 2. S04 / S11 通路

S04：

- U50 74HCT541：`A0..A5=SCORE_ADDR0..5`，`A6/A7=GND`，`Y0..Y7=ADDR0..7`，OE=`ARGMAX_BUSY_N`。
- U51 74HCT541：`A0..A7=GND`，`Y0..Y7=ADDR8..15`，OE=`ARGMAX_BUSY_N`。
- U40/U41 仍是 `ADDR -> MADDR` 的唯一缓冲。

S11：

- 74HC148 U1 的 I3 接 `ARGMAX_BUSY_N`；输出 S2 变为 `MASTER2`。
- 27C512 U5 的 A7 接 `MASTER2`。地址公式变为 `A[7:0]={MASTER2,FC_SEL,MASTER[1:0],REGION[2:0],0}`。
- 映射 ROM 对 master=4 的所有 `{fc_sel,region}` 写 `MEM_SEL=6`；原 C1/C2/FC 地址不变。
- `REQ = C1_REQ | C2_REQ | FC_REQ | SCORE_RD`；新增 U12 74HC32 完成合并。`WE` 不含 Argmax（只读）。

## 3. S12 时序

- 74HC238 E3=`MEM_ACK`；`A0/A1=SCORE_ADDR0/1`（字节 lane）。
- S02 读事务：`SETUP -> WAIT -> CAPTURE`，CAPTURE 时 `MEM_ACK` 有效，SRAM 数据已稳定；四个 574 在该沿锁存对应字节。
- S06 在 `S_WT` 等 ACK 后撤销 `SCORE_RD`，继续等 `MEM_DONE`；S02 完整走完 `HOLD/RELEASE/DONE` 后才允许下一字节。

## 4. Harness

`sim/harness_argmax_s12.py`：

1. **结构检查**：从 `output/top.net` 检查
   - `SCORE_ADDR0..5`：S06 U6038 输出、S04 U4050 输入、S12 U13006 A0/A1；
   - `BYTE0/1`：U6039 Q0/Q1 → U6038 A0/A1；
   - `MEM_ACK`：S02 U2005、S12 U13006 E3、S06 U6045；
   - `WT_HOLD`/`BD_HOLD`/`D_BYTE_DONE` 保持逻辑；
   - `ARGMAX_BUSY_N`：S06 U6042、S11 U12001 I3、S04 U4050/U4051 OE；
   - `MASTER2`：S11 U12001 S2 → U12005 A7；
   - `SCORE_RD`：S11 REQ 合并。
2. **行为检查**：周期模型跑 3 组 32 位向量（正数/负数/并列），验证
   - 40 个字节地址严格为 `4*class+byte`；
   - 40 次 ACK + 40 次 DONE；
   - S12 四 lane 拼装出正确的 little-endian 字；
   - signed32 argmax（含并列取小编号）。

输出：

```
PASS: structural Argmax/S12/S04/S11 connections
PASS: 4-byte address sequence + S12 latches, argmax=3
PASS: 4-byte address sequence + S12 latches, argmax=2
PASS: 4-byte address sequence + S12 latches, argmax=2
PASS: S06/S04/S12 Argmax four-byte transaction
```

## 5. 复现

```bash
python tools/gen_bus_map.py
python tools/build_argmax.py
python tools/build_s12.py
python tools/build_memories.py
python tools/build_bus.py
python tools/renumber_refs.py
python tools/strip_pwr_flags.py
python tools/build_top.py
kicad-cli sch export netlist --format kicadsexpr -o output/top.net CNN_74xx_System.kicad_sch
python tools/audit_top_connectivity.py output/top.net
kicad-cli sch erc --severity-all -o output/top-erc-final.rpt CNN_74xx_System.kicad_sch
python sim/run_all.py
```

## 6. 未完成

- Requant 门级展开（M-05/M-09）、LUT 物理 lane 映射（M-08）、10–100 Hz 时序重算（M-10）、BOM 封装（M-11）、S02 未用译码输出（M-13）。
- 顶层仍有 3 个单节点：`FC_MODE_SPARE`、`ARGMAX_RESULT_VALID`、`POOL_BUSY`（状态回送/备用）。
