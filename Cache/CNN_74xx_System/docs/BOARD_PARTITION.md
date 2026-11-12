# 12 板卡划分（方案 A）

每块板卡是独立的物理板；引擎不再跨阶段复用，层与层之间的差异用板上固定连线和独立网络前缀实现。底板只做无源互连，引脚定义见 `output/backplane/backplane_pinout.csv`。

| 板卡 | 名称 | 功能 | 图页 | 对外网络 | 排针 |
|---|---|---|---|---|---|
| BB01 | SUPERVISOR | Global supervisor FSM, microcode ROM, watchdog | S, 0, 1, _, S, u, p, e, r, v, i, s, o, r, ., k, i, c, a, d, _, s, c, h | 37 | 2 x 2x20P (52 pins) |
| BB02 | TIMING | Memory timing controller SETUP/WAIT/CAPTURE/HOLD/RELEASE | S, 0, 2, _, T, i, m, i, n, g, ., k, i, c, a, d, _, s, c, h | 10 | 1 x 2x20P (26 pins) |
| BB03 | MEMORY | 7x 6264 SRAM + 12x 28C256 + 8x 27C512 LUT/map storage | S, 0, 4, _, M, e, m, o, r, i, e, s, ., k, i, c, a, d, _, s, c, h | 204 | 8 x 2x20P (208 pins) |
| BB04 | CONV1 | 5x5x1 -> 8ch convolution engine + ACC>>8 requant | S, 0, 7, _, C, o, n, v, 1, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 3, _, R, e, q, u, a, n, t, _, C, 1, ., k, i, c, a, d, _, s, c, h | 43 | 2 x 2x20P (52 pins) |
| BB05 | POOL1 | 2x2 stride-2 max pool 12x12x8 -> 6x6x8 | S, 0, 5, _, P, o, o, l, 1, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 2, A, _, P, o, o, l, L, a, t, c, h, 1, ., k, i, c, a, d, _, s, c, h | 53 | 3 x 2x20P (78 pins) |
| BB06 | CONV2 | 3x3x8 -> 16ch convolution engine + ACC>>9 requant | S, 0, 8, _, C, o, n, v, 2, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 5, _, R, e, q, u, a, n, t, _, C, 2, ., k, i, c, a, d, _, s, c, h | 43 | 2 x 2x20P (52 pins) |
| BB07 | POOL2 | 2x2 stride-2 max pool 10x10x16 -> 5x5x16 | S, 0, 5, _, P, o, o, l, 2, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 2, A, _, P, o, o, l, L, a, t, c, h, 2, ., k, i, c, a, d, _, s, c, h | 53 | 3 x 2x20P (78 pins) |
| BB08 | FC1 | 400 -> 32 fully connected + FC1 uint8 requant | S, 0, 9, _, F, C, 1, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 7, _, F, C, 1, ., k, i, c, a, d, _, s, c, h | 43 | 2 x 2x20P (52 pins) |
| BB09 | FC2 | 32 -> 10 fully connected + FC2 raw signed32 requant | S, 0, 9, _, F, C, 2, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 7, _, F, C, 2, ., k, i, c, a, d, _, s, c, h | 44 | 2 x 2x20P (52 pins) |
| BB10 | ARGMAX | 10-way signed-32 argmax + 32-bit score staging | S, 0, 6, _, A, r, g, m, a, x, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 2, B, _, S, c, o, r, e, L, a, t, c, h, ., k, i, c, a, d, _, s, c, h | 26 | 1 x 2x20P (26 pins) |
| BB11 | BUSFAB | Master/region encode, map ROM, REQ/WE merge, engine merge | S, 1, 1, _, B, u, s, F, a, b, r, i, c, ., k, i, c, a, d, _, s, c, h, ;, S, 1, 1, A, _, E, n, g, i, n, e, M, e, r, g, e, ., k, i, c, a, d, _, s, c, h | 72 | 3 x 2x20P (78 pins) |
| BB12 | HOSTIO | Host connector, clock/reset, image and weight load ports | S, 1, 0, _, T, o, p, _, I, O, ., k, i, c, a, d, _, s, c, h | 59 | 3 x 2x20P (78 pins) |

## 电源引脚（所有排针一致）

| 引脚 | 网络 |
|---|---|
| 1-4 | +5V |
| 5-8 | +3V3（预留） |
| 9-14 | GND |
| 15-40 | 信号（每排针 26 根） |

## 板内网络（不上底板）

- `C1_ACC*` / `C1_REQ_*`：B04（S07+S13）
- `C2_ACC*` / `C2_REQ_*`：B06（S08+S15）
- `FC1_ACC*` / `FC1_REQ_*`：B08（S09_FC1+S17_FC1）
- `FC2_ACC*` / `FC2_REQ_*`：B09（S09_FC2+S17_FC2）
- `IN_DATA1*`：B05（S05_Pool1+S12A_PoolLatch1）
- `IN_DATA2*`：B07（S05_Pool2+S12A_PoolLatch2）
- `SCORE_DATA*`：B10（S06+S12B_ScoreLatch）

## 复用消除后的固定选择

- POOL1 板 `POOL_SEL` 固定 0；POOL2 板 `POOL_SEL` 固定 1。
- FC1 板 `FC_SEL` 固定 0；FC2 板 `FC_SEL` 固定 1。
- `FC_SEL` / `POOL_SEL` 仍由 S01 送 B11 的 map ROM，用于选择权重/输出窗口；它们不再进入引擎板。
- B11 的 S11A 用 `FC2_BUSY` / `POOL2_BUSY` 把两套引擎信号二选一送回 S11 的单一 FC/POOL 槽位。

## 工程文件

- 交接说明（转嘉立创 EDA）：`docs/BOARD_HANDOFF.md`
- 板卡清单：`output/boards/BOARD_MANIFEST.csv`
- 网络-板卡矩阵：`output/boards/backplane_nets.csv`
- 逐引脚定义：`output/backplane/backplane_pinout.csv`
