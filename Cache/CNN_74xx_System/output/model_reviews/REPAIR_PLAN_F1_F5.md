# 已独立复现的修复计划（F1/F5 小修，待模型报告确认后应用）

日期：2026-11-05
证据：`output/visual_fix/after/top.net`、`output/visual_fix/after/top.audit.json`
状态：主工程尚未修改；等五份模型报告到齐后，若至少两份独立确认或主进程复现成立，则应用。

## 修复 1：Pool/Argmax 的阶段启动脉冲

现状：
- S01 U1008 输出 `P1_START`(pin17)、`P2_START`(pin15)、`ARGMAX_START`(pin12)，但顶层网表中每个只有 1 个节点。
- S05 Pool 的 U36/U37 启动门使用通用 `START`；S06 Argmax 的 U36b/U37b 也使用 `START`。
- 因此 S01 的阶段启动脉冲没有到达 Pool/Argmax；它们会跟随主机 `START`，而不是 FSM 的 P1/P2/ARGMAX 阶段。

修复：
1. `tools/build_pool.py`
   - 增加 `P1_START`、`P2_START` 两个全局输入。
   - 增加一个 74HC32 或门（建议新位号 U42）：
     `U42a: 1=P1_START, 2=P2_START, 3=POOL_START`
   - 把 U36.1、U37.5 的 `START` 改为 `POOL_START`。
   - 从 S05 的 `GLOBAL_NETS` 移除不再使用的 `START`（如果确认没有其它负载）。
2. `tools/build_argmax.py`
   - 把 U36b.4、U37b.5 的 `START` 改为 `ARGMAX_START`。
   - `GLOBAL_NETS` 用 `ARGMAX_START` 替换 `START`。
   - 更新接口说明/注释。
3. 重新生成 S05、S06、顶层；`P1_START/P2_START` 应各有 2 个节点（U1008 + U42），`ARGMAX_START` 应有 2 个节点（U1008 + S06 门）。

## 修复 2：Pool 的 DONE 多驱动

现状：
- 顶层 `DONE` 网络同时有 `U1009.17`（S01 74HCT541 Y1，OE=GND）和 `U5039.17`（S05 74HCT541 Y1，OE=GND），两个推挽输出直接相连。
- S05 的 U41 与门用 `DONE` 生成 `P1_DONE/P2_DONE`，因此不能简单删除。

修复：
1. `tools/build_pool.py`
   - U39 的 `Y1` 输出从 `DONE` 改为页内 `POOL_DONE`。
   - U41/U41b 的输入从 `DONE` 改为 `POOL_DONE`。
   - S05 `GLOBAL_NETS` 移除 `DONE`；`P1_DONE/P2_DONE` 保持全局。
2. 顶层 `DONE` 只保留 S01 `U1009.17` 一个 74HCT541 输出；S10 U10097.3 是输入，不算驱动。
3. 重新跑 `tools/audit_top_connectivity.py`，`done_74hct541_outputs` 应为 1，`done_multidriver=false`。

## 验证

```bash
python tools/build_pool.py
python tools/build_argmax.py
python tools/promote_engine_status.py
python tools/renumber_refs.py
python tools/strip_pwr_flags.py
python tools/build_top.py
python tools/export_review.py
python sim/run_all.py
python tools/audit_top_connectivity.py output/visual_fix/after/top.net
```

期望：
- `sim/run_all.py` 仍 9/9 PASS（模块级行为测试不应受跨页 START/DONE 改名影响；若 testbench 引用旧网名，需同步更新）。
- `P1_START/P2_START/ARGMAX_START` 不再出现在 single-node 列表。
- `DONE` 不再 multi-driver。
- `C1/C2/FC_ADDR`、`Cx_MEM_nCE_*`、`MEM_DATA/ACK/DONE/BUSY` 仍会是 single-node，这是下一阶段总线 owner 的工作，不在本小修范围内。

## 不在本小修范围

- F2/F3：引擎到 S04/S02 的地址/片选/数据/应答总线。
- F4：POOL_BUSY/ARGMAX_RESULT_VALID 的状态回送（先确认是否设计上需要）。
- LUT/S02/Requant 层次展开。
