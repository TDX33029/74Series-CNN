# V19–V26 落地复核 + 重仿真验证报告（2026-11-13）

对象：嘉立创工程 `74CNN-BRD`（按 `CHANGES_V2_BOARD_FIX_APPLIED_2026-11-13.md` 完成的 74 处改动）
方法：不依赖落地报告本身，直接从运行中的嘉立创工程重新抓取引脚网络，再从改后状态重建仿真全流程重跑。

## 1. 活工程独立复核（EasyEDA 在线抓取）

- 74 处改动引脚（原理图）：74/74 与变更清单一致，含 8 处"必须空脚"全部确认悬空。
- 18 处改名/新网络的消费端引脚：18/18 网名逐字符一致。关键项
  `FC_N400A_13` 驱动端（U9020.1 / U9220.1）与消费端（U9024.3 / U9224.3）
  大小写完全一致，没有断线；Pool 两板的 V 计数器页名实际为
  b05-1_pool1 / b07-1_pool2，四只 S_WT 引脚同样正确。
- PCB 焊盘侧 10 个排针改动（背板点对点接线落点）：10/10 一致
  （J20304.50、J20801.3/4、J20804.16/17/62、J20805.13/14、J20806.58/59）。
- 复核数据：`D:/tmp/jlc_brd/state/fix_2026-11-13/recheck_zcode.json`、
  `recheck2_zcode*.json`、`recheck_pcb_zcode.json`。

## 2. 仿真流水线从改后状态重建（可复现性）

- `patch_netlist_bclass.py --apply` 重新生成 `top_20261112c.net`：
  sha256 与上一轮 8/8 通过时逐字节相同（ed06893e…）。
- `build_analysis.py` → `gen_rtl.py` → `apply_scheme_c_eco.py`（8 个 XOR3）：
  `cnn74_top.v` sha256 与上一轮相同（b6f055ee…）。
- 结论：EDA 现状 == 仿真模型，仿真结果即板卡逻辑的验证结果。

## 3. 重仿真（8 组向量，全核并行）

tb_numeric 增加 `+vfirst=K` / `+wbase=S` 参数（有备份 tb_numeric.v.pre_vfirst），
每个向量一个独立 vsim 进程、独立编译库，8 核并行。墙钟时间 30 分钟 → 约 4 分半。

- 判定：VECTOR 0..7 全部 PASS，每进程 `1/1 vectors pass, 0 total errors`。
- 写周期归属：每向量 `C1=4608 C2=1600 FC=72 POOL=1552 none=1`（无重复/漏写）。
- 逐层逐字节比对（8 向量 × 6 层全部 OK）：

  | 层 | 每向量字节数 | 结果 |
  |---|---|---|
  | C1OUT  | 4608 | OK |
  | P1OUT  | 1152 | OK |
  | C2OUT  | 1600 | OK |
  | P2OUT  | 400  | OK |
  | FC1OUT | 32   | OK |
  | FC2 logits（int32 little-endian） | 10 | OK |

- 比对脚本：`Simulation/rtl/compare_par.py`；日志：`Simulation/rtl/sim_v*/sim.log`；
  产物：`sim_v*/dump_*.hex`；运行脚本：`Simulation/rtl/run_par.sh`。

## 3.1 向量集扩充到 16 组（投板前加固）

numpy 参考模型（`Simulation/gen_vectors.py`）从 hex 权重重建，先对原 8 组
向量逐位复现 exp 文件（REFERENCE MODEL VALID）后，新增 8 组向量 8..15：

- 向量 8：全 0 图（logits 全 0，钳位下限路径）
- 向量 9：全 255 图（满动态范围）
- 向量 10：固定种子随机噪声图
- 向量 11/13/15：MNIST 测试集数字 8（三张不同图，均分类正确）
- 向量 12/14：数字 9（两张不同图，均分类正确）

板卡网表仿真 8 组全部 PASS，6 层输出逐位一致（compare_par.py 8..15
ALL LAYERS BYTE-EXACT: True）。tb 的 argmax 校验已从"向量号=数字"假设
改为与期望模型 argmax 对齐（备份 tb_numeric.v.vfirst_wbase）。
现有回归覆盖：16 组向量 × 6 层，全部逐位一致。

## 4. 结论

嘉立创工程的 V19–V26 + V16 补漏 + U7157 修正与变更清单逐引脚一致；
修改后的 47 板逻辑在全部 8 组测试向量上与软件模型逐位一致。
板卡逻辑功能已验证，可以投产。剩余烧录项不变（LUT 有符号表、
c1_rom1/c2_rom1、fc_rom2、V2 权重），见落地报告第 4 节。

提示一点（非错误，落地报告 3.3 已记录）：B09-1 的 GND 排针从 4 脚减到
2 脚（p3/p4 改作 FC2 字节选择），B09-6 从 7 脚减到 5 脚。若背板 GND 电流
余量紧张，投板前可评估一下这两处的回流路径。
