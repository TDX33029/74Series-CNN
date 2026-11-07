# 互联方案交付包（Agent Handoff）

本目录是给实现 agent 的入口。先读 `docs/INTERCONNECT_PLAN.md`，再用
`interconnect_plan.csv` 做机器可读核对。

## 文件

| 文件 | 用途 |
|---|---|
| `docs/INTERCONNECT_PLAN.md` | 完整方案：端口契约、118 条网络、S11/S04 Pool 架构、A/B 修复、FSM 微码、验收标准、agent 提示词 |
| `output/interconnect/interconnect_plan.csv` | 逐网络表：net,width,source,dest,active,timing,status,notes |
| `output/interconnect/pool_bus_path.png` | Pool 总线示意图（S05 → S11/S02 → S04） |
| `output/integration/` | 各 agent 的报告输出目录 |

## 先看结论

1. **不能只画顶层连线**：S05 缺 5 个总线控制 + `MEM_ACK/MEM_DONE` 握手；S07/S08/S09 的 A/B 都接 `DATA`（LUT 算 `x*x`），且 574 流水线自由跑、等待态会错位；本地 FSM ROM 没有镜像；12 个 LUT 块未展开。
2. Pool 作为 S11 的第 5 个 master：S11 只做 map/REQ/WE/region，低 16 位地址和写数据在 S04 用 5×74HCT541 + 1×74HC32 缓冲/读 OE。
3. S11 只加 1×74HC157（第三级 region mux）；S04 加 5×74HCT541 + 1×74HC32；S05 复用 U39/U40 空闲门，基本不增芯片。
4. A/B 推荐方案 A：A/B 输入锁存 + 8 个寄存器级的保持 mux（保留现有计数器/ACC 时序）；8 级 FIFO 方案需重写地址/ACC，风险高。
5. LUT 展开推荐 24 片独立（每引擎 8 片），8 片共享作为后续降本；先拍板再发 A6。

## 发任务顺序

```text
A1 顶层集成（可先做）
A2 + A3 + A3b  Pool 总线（S05 + S11 + S04）
A4 + A5        引擎 A/B + 本地 FSM
A1 复跑        顶层连线/ERC
A7             集成验证
A6             LUT 物理展开（PCB 前）
A8             文档/PDF
```

## 每个 agent 的硬约束

- 只改自己负责的 `.kicad_sch` 和 builder；不要改别人的图。
- 跨模块网络名以 `docs/INTERCONNECT_PLAN.md` 第 3 节和 CSV 为准；新增网络先加 CSV。
- 必须用 `global_label`，不允许用同名 `local_label` 绕过跨页连接。
- 不允许把两个输出直接短接；总线冲突必须靠三态/使能解决。
- 修改后跑：

```bash
python tools/renumber_refs.py
python tools/strip_pwr_flags.py
python tools/build_top.py
python tools/export_review.py --no-preview
python sim/run_all.py
```

## 验收门槛

- 顶层 ERC 0 error；除显式 `TP_*` 外无单节点模块边界网。
- `DATA[7:0]` 同时只有一个驱动；`POOL_MEM_nCE_IN/OUT` 不同时为低。
- Pool 读 4 字节/写 1 字节通过；Conv/FC 的 `PROD=A*B`，不是 `x*x`。
- BOM 不再有 `LUT_Mult_Unit` 块符号；DIP/BOM/ERC 数更新到文档。
