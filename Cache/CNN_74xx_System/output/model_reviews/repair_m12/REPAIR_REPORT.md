# repair_m12 报告：S08 CONV2 输入地址 HWC -> CHW

日期：2026-11-05
隔离工作副本：`D:/Document/tempPrj/74Series-CNN/Cache/_repair_m12/work`
报告目录：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/model_reviews/repair_m12`

## 1. 结论

已完成隔离修复，主工程源文件未修改。

- S08 CONV2 输入地址由 HWC 改为 CHW：
  `IN_ADDR = ic*144 + (oy+ky)*12 + (ox+kx)`，范围 0..1151。
- `sim/gen_engine_tb.py` 的 golden 与 SPICE B 源同步改为 CHW。
- 重新生成 S08 后，`sim/gen_engine_tb.py` 的 CONV1/CONV2/FC 全部 `RESULT: PASS`，`OVERALL: PASS`。
- `sim/run_all.py`：**9/9 PASS**。
- 布局 harness：POOL1_OUT -> CONV2 修正前 `FAIL`（7200 个读地址中 7198 个错误，仅 2/1152 字节按自身地址读回），修正后 **PASS**（7200/7200 正确，0 failures）。
- 顶层网表：C2 IN_ADDR 逻辑存在，11 位每位 2 个节点；新增地址网络无单节点总线；单节点网络总数 525 -> 525，未新增。
- 74HC283 总数保持 **52 -> 52**；输入地址块仍为 8 片 74HC283（与旧实现相同）。移除 4 个 SY 反相器后，74HC04 符号单元由 6 个降为 2 个（物理封装仍为 1 片）。
- 权重地址、输出地址、循环顺序、MAC 数量均未改变；无需连带修改 S04/S05/S07/S09。

## 2. 依据与错误确认

任务书 `CNN_74xx_MNIST_28x28_v1.txt` 第 2.1 节规定所有多通道特征图统一 CHW：

```text
ADDR(c,y,x) = c*H*W + y*W + x
POOL1_OUT: ADDR_P1(c,y,x) = c*12*12 + y*12 + x = c*144 + y*12 + x
```

S08 原图纸文字与实际加法器均为 HWC：

```text
IN_ADDR = (oy+ky)*96 + (ox+kx)*8 + ic
```

而 S05 Pool1 输出为 `OUT_ADDR = c*144 + y*12 + x`。两者不一致，确认是真实地址布局错误。布局 harness 在修正前给出的首个反例：POOL1 在 channel 0 `(y=0,x=1)` 写入地址 1，CONV2 却从地址 8 读取；1152 个 POOL1 字节中只有 2 个能被正确读回。

## 3. 改动文件

| 文件（work 根目录相对路径） | 改动 | 是否进入 m12.patch |
|---|---|---|
| `tools/build_conv2.py` | 输入地址加法器改为 CHW；更新图纸文字，删除 HWC 说法 | 是 |
| `sim/gen_engine_tb.py` | `golden_conv2()` 与 `spice_conv2()` 的输入地址公式改为 CHW | 是 |
| `S08_Conv2.kicad_sch` | 由修改后的 builder 重新生成 | 是 |
| `docs/REPORT_Conv_FC.md` | CONV2 地址公式文档同步为 CHW | 是 |
| `output/model_reviews/muse-slot-session-model/harness_datapath_layout.py` | 工作副本中的测试 oracle：`conv2_in()` 改为 CHW（主工程原文件未改） | 否，报告第 7 节给出 diff |

没有修改顶层 `.kicad_sch`。顶层握手网表保持原样，见第 8 节。

S08 重新生成后，按项目既有后处理流程执行了以下未修改脚本，以维持工程约定：

```bash
python tools/strip_pwr_flags.py        # 移除重新生成时带入的 2 个 per-sheet PWR_FLAG
python tools/renumber_refs.py          # S08 引用恢复到 U8001..U8151 区块
python tools/promote_engine_status.py  # C2_DONE_I/C2_BUSY_I 提升为全局 C2_DONE/C2_BUSY
```

这三步只处理项目原有约定，不改变地址逻辑。若从 `build_conv2.py` 再次重建 S08，必须按上述顺序执行，否则会丢失全局 DONE/BUSY 标签或引入重复位号。

## 4. 地址公式前后对比

| 信号 | 修改前 | 修改后 | 说明 |
|---|---|---|---|
| `SY` | `OY+KY` | `OY+KY` | 0..11 |
| `SX` | `OX+KX` | `OX+KX` | 0..11 |
| `SY96` | `SY*128 - SY*32` | 删除 | 旧实现另有算术缺陷，见第 10 节 |
| `SY12` | 不存在 | `8*SY + 4*SY` | 2 级 74HC283，0..132 |
| `IC9` | `8*IC + IC` | `8*IC + IC` | 原有网络保留，0..63 |
| `IC144` | 不存在 | `IC9 << 4`，低 4 位接 GND | 0..1008 |
| `T1` | 不存在 | `IC144 + SY12` | 3 级 74HC283，0..1140 |
| `SXI` | `(SX<<3) + IC` | 删除 | |
| `IN_ADDR` | `SY96 + SXI` = `(oy+ky)*96 + (ox+kx)*8 + ic` | `T1 + SX` = `ic*144 + (oy+ky)*12 + (ox+kx)` | 11 位，0..1151 |
| `W_ADDR` | `oc*72 + ic*9 + ky*3 + kx` | 不变 | 与任务书 2.2 节 `W2[oc][ic][ky][kx]` 一致 |
| `OUT_ADDR` | `oc*100 + oy*10 + ox` | 不变 | 与任务书 2.1 节 `ADDR_C2` 一致，本身已是 CHW |

图纸文字同时修正：

- `Input layout HWC C=8` -> `Input layout CHW C=8`，并写入新公式。
- `Output layout HWC C=16` -> `Output layout CHW C=16`（公式本来就是 `oc*100+...`，只是文字标签错误，无硬件改动）。

## 5. 硬件实现与结构验证

输入地址块使用 8 片 74HC283：

- `SY = OY + KY`：1 片。
- `SX = OX + KX`：1 片。
- `SY12 = (SY<<3) + (SY<<2)`：2 片。
- `IC9 = (IC<<3) + IC`：2 片（该网络同时供权重地址使用，未新增）。
- `T1 = IC144 + SY12`，其中 `IC144` 低 4 位直接接 GND：3 片。
- `INA = T1 + SX`：3 片。

顶层网表结构追踪（work 的 `output/top.net`）：

| 检查项 | 结果 |
|---|---|
| `C2_IN_ADDR0..10` 节点数 | 每位 2 个节点（74HC283 输出 + 74HC157 I0 输入），无单节点 |
| `C2_SY12_0..7` / `C2_SY12_C0` | 每个 2 节点 |
| `C2_T1_0..10` / `C2_T1_C0` / `C2_T1_C1` | 每个 2 节点 |
| `C2_IC9_0..3` | 除 IC9 加法器输出和权重地址使用外，还连接到 T1 第二级 74HC283 的 A1..A4，即 T1 的 bit4..bit7 |
| `C2_IC9_4..5` | 连接到 T1 第三级 74HC283 的 A1/A2，即 T1 的 bit8/bit9 |
| `C2_IN_ADDR` 驱动 | T1 加法器输出 -> 74HC157 I0 -> `C2_ADDR` 缓冲链 |
| 74HC283 数量 | 旧 52 片，新 52 片 |
| 74HC04 符号单元 | 旧 6 个（5 个反相门 + 电源单元），新 2 个（1 个反相门 + 电源单元）；物理芯片均 1 片 |
| S08 参考位号 | U8001..U8151，共 151 个，与旧文件区间一致 |

此外对全部 7200 个 `(oy,ky,ox,kx,ic)` 组合做了位级加法器穷举：新链路输出与 `ic*144+(oy+ky)*12+(ox+kx)` 完全一致，最大值 1151。

## 6. 仿真结果

执行命令与结果：

```bash
cd D:/Document/tempPrj/74Series-CNN/Cache/_repair_m12/work
python sim/gen_engine_tb.py
python sim/run_all.py
```

`sim/gen_engine_tb.py`：

```text
CONV1: RESULT: PASS
CONV2: RESULT: PASS
FC:    RESULT: PASS
OVERALL: PASS
```

CONV2 关键断言：

```text
PASS: CONV2 IN_ADDR bounds 0..1151 (got 0..1151)
PASS: CONV2 last addresses = (1151,1151,1599)
PASS: conv2: SPICE address sequence equals golden for every step
PASS: conv2: SPICE extrema equal golden extrema
PASS: conv2: MAC count 115200 == 115200
RESULT: PASS
```

`sim/run_all.py`：

```text
9/9 checks passed
  PASS  lut_contents
  PASS  lut_spice
  PASS  glue
  PASS  supervisor
  PASS  timing
  PASS  mem_decode
  PASS  pool
  PASS  argmax
  PASS  conv_fc_engines
```

`gen_engine_tb.py` 只改了以下两处公式，其他 golden、断言和计数模型未改：

```diff
-                                (oy + ky) * 96 + (ox + kx) * 8 + ic,
+                                ic * 144 + (oy + ky) * 12 + (ox + kx),
```

```diff
-        "Bina ina 0 V = (V(oy)+V(ky))*96+(V(ox)+V(kx))*8+V(ic)",
+        "Bina ina 0 V = V(ic)*144+(V(oy)+V(ky))*12+(V(ox)+V(kx))",
```

## 7. 布局 harness 结果

harness 从主工程复制到工作副本临时路径：

`work/output/model_reviews/muse-slot-session-model/harness_datapath_layout.py`

该脚本的 `conv2_in()` 原本按 S08 旧图纸文字编码，属于“生产者公式”的镜像，而不是独立 oracle。修正前运行结果（保留旧公式）：

```text
-- POOL1_OUT (S05) -> CONV2 input (S08) --
FAIL: all 7200 CONV2 input reads hit the POOL1 byte (bad=7198, first=(0, 0, 1, 8, 1))
  MISMATCH: e.g. POOL1 wrote channel 0 at (y=0,x=1) address 1, but CONV2 reads address 8
  only 2/1152 POOL1 bytes are read back at their own address

RESULT: FAIL (1 failures)
```

将工作副本 harness 的 `conv2_in()` 同步为修正后的 S08 公式后：

```text
-- POOL1_OUT (S05) -> CONV2 input (S08) --
PASS: all 7200 CONV2 input reads hit the POOL1 byte (bad=0, first=None)

-- CONV2_OUT (S08) -> POOL2 input (S05) --
PASS: all 1600 POOL2 reads hit the CONV2 byte (bad=0)

-- POOL2_OUT (S05) -> FC1 input (S09) --
PASS: all 400 FC1 reads hit the POOL2 byte in CHW order (bad=0)

RESULT: PASS (0 failures)
```

工作副本 harness 的唯一改动：

```diff
 def conv2_in(oc, oy, ox, ic, ky, kx):
-    # S08 sheet note: "Input layout HWC C=8: IN_ADDR=(oy+ky)*96+(ox+kx)*8+ic"
-    return (oy + ky) * 96 + (ox + kx) * 8 + ic
+    # S08 sheet note (repair_m12): "Input layout CHW C=8:
+    # IN_ADDR=ic*144+(oy+ky)*12+(ox+kx)"
+    return ic * 144 + (oy + ky) * 12 + (ox + kx)
```

主工程的 harness 文件未被修改；后续若把本修复合并回主工程，必须同步更新主 harness 的 `conv2_in()`，否则它仍会按旧公式判 FAIL。

## 8. 顶层网表导出与单节点总线检查

导出命令：

```bash
cd D:/Document/tempPrj/74Series-CNN/Cache/_repair_m12/work
"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist \
  -o output/top.net CNN_74xx_System.kicad_sch
```

kicad-cli 输出的“原理图存在批注错误”警告在主工程导出时同样存在，是既有状态，不是本次改动引入。

S08 网表网络集合差异（旧顶层网表 vs 新顶层网表）：

```text
移除（旧地址实现）：
  C2_NSY0..3                     4
  C2_SXI0..7, C2_SXI_C0          9
  C2_SY96_0..10, C2_SY96_C0/C1  13
新增（CHW 实现）：
  C2_SY12_0..7, C2_SY12_C0       9
  C2_T1_0..10, C2_T1_C0/C1      13
```

除上述地址网络外，S08 没有其他网络增删；S08 网络数 577 -> 573。

单节点总线检查：

- `C2_IN_ADDR0..10`、`C2_SY12_*`、`C2_T1_*` 全部为 2 节点网络。
- 单节点网络总数：旧 525，新 525。
- 新旧单节点集合的 42 个差异全部是 `unconnected-(U8xxx-...)` 因重新编号产生的名称位移（例如 U8140 -> U8139），不是地址网络，也没有新增悬空总线。
- 全局握手网保持：`C2_START` 3 节点、`C2_DONE` 3 节点，与修改前一致。`C2_BUSY` 在修改前后均为 1 节点（既有状态，见剩余风险）。

ERC 对照（同一 KiCad 10.0.4，baseline S08 用同工具重跑）：

| 项目 | 旧 S08 | 新 S08 |
|---|---|---|
| violations 总数 | 193 | 189 |
| errors | 5 | 5 |
| warnings | 188 | 184 |

5 个 error 类别完全一致：2 个是单页导出时 PWR_FLAG 已在层级层移除导致的电源引脚未驱动，3 个是既有的输入未驱动（U8001 CP、U8016 pin1、U8139 A5；旧文件对应 U8140 A5）。warning 减少 4 条，来自删除 4 个 SY 反相器后 `lib_symbol_mismatch` 减少。未新增 ERC 类别。

## 9. 连带影响分析

结论：CHW 修复只影响 S08 输入读地址，不影响权重、输出或其它阶段。

- 权重布局：任务书 2.2 规定 `W2[oc][ic][ky][kx]`，`ADDR_W2 = (((oc*8+ic)*3+ky)*3+kx) = oc*72+ic*9+ky*3+kx`。S08 的 `W_ADDR` 与此完全一致，未改。
- 输出布局：任务书 `ADDR_C2(oc,y,x) = oc*10*10 + y*10 + x`。S08 的 `OUT_ADDR = oc*100+oy*10+ox` 与此一致，未改。harness 的 CONV2_OUT -> POOL2 边界仍 PASS。
- 循环顺序：`oc -> oy -> ox -> ic -> ky -> kx` 未改；MAC 总数 115200 未改。
- S05 Pool1 写地址、S07 Conv1、S09 FC 均未改；顶层 `.kicad_sch` 未改。
- 输出顺序和写时序未改，故没有因输入布局改变而需要调整的权重/偏置/qparam 地址。

因此本次不需要“先停下来”的连带影响处理。

## 10. 附带发现：旧 SY96 链本身还有算术错误

旧实现：

```text
SY96 = SY*128 - SY*32
a = {GND x7, SY[3:0]}       (SY<<7)
b = {GND x5, ~SY[3:0]}      (~SY<<5)
cin = +5V
```

按实际 74HC283 链逐位求值，结果为 `96*SY + 481`，并非 `96*SY`：

| SY | 旧链输出 | 正确 96*SY | 偏差 |
|---:|---:|---:|---:|
| 0 | 481 | 0 | +481 |
| 1 | 577 | 96 | +481 |
| 6 | 1057 | 576 | +481 |
| 11 | 1537 | 1056 | +481 |

原因是二补码减法只反相了 4 位 SY 并在 bit0 注入 +1，缺少高位/低位的符号填充，留下常数偏移。该缺陷与 HWC/CHW 错误叠加，使旧 S08 的实际输入地址既布局错误又带 +481 偏移。本次按任务建议用 `SY12 = 8*SY+4*SY` 完全替换 SY96 链，因此同时消除了该偏移。未对其它模块做修改。

## 11. 剩余风险

1. **组合路径加深**：旧 SY 路径为 `SY(1) + SY96(3) + INA(3) = 7` 级 74HC283；新路径为 `SY(1) + SY12(2) + T1(3) + INA(3) = 9` 级，增加约 2 级传播延迟（按典型 74HC283 tpd 约 40-50 ns 量级）。8 MHz 周期为 125 ns，是否满足建立时间需要在门级或实物上确认；本次只做了行为级地址序列和位级穷举，没有做门级时序仿真。
2. **harness oracle**：主工程 harness 仍编码旧公式。合并修复时必须同步更新，否则会误报 FAIL。本报告只改了工作副本。
3. **S08 重新生成的影响**：UUID 全部变化，位号经项目脚本重排；patch 因此较大（约 1.1 MB）。若下游脚本或人工检查按旧 S08 位号定位器件，需要重新核对。功能网表除地址网络外无差异。
4. **既有单节点 `C2_BUSY`**：顶层网表中修改前后均为 1 节点。它不是本次引入，但说明该状态线目前没有顶层消费者；建议在顶层集成评审中单独确认。
5. **单页 ERC 电源错误**：由于工程在层级层集中放置 PWR_FLAG，单页 S08 ERC 会出现 2 个电源引脚未驱动错误；属于既有流程现象。顶层 ERC 仍需在集成阶段执行。
6. **行为级 SPICE 不覆盖门延迟**：`gen_engine_tb.py` 的 SPICE 是行为级地址序列，不能证明 74HC283 链的时序；链的正确性由网表结构追踪和 7200 组位级穷举保证。

## 12. 复现步骤

从主工程重新建立隔离副本后的完整命令：

```bash
cd D:/Document/tempPrj/74Series-CNN/Cache/_repair_m12/work
python tools/build_conv2.py
python tools/strip_pwr_flags.py
python tools/renumber_refs.py
python tools/promote_engine_status.py
python sim/gen_engine_tb.py
python sim/run_all.py

# 布局 harness（从主工程复制到临时路径后，将 conv2_in 改为 CHW）
mkdir -p output/model_reviews/muse-slot-session-model
cp <main>/output/model_reviews/muse-slot-session-model/harness_datapath_layout.py \
   output/model_reviews/muse-slot-session-model/
# 修改 conv2_in 后：
python output/model_reviews/muse-slot-session-model/harness_datapath_layout.py

# 顶层网表
"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist \
  -o output/top.net CNN_74xx_System.kicad_sch
```

## 13. 补丁与校验值

- patch：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/model_reviews/repair_m12/m12.patch`
- 相对 work 根目录，包含：`tools/build_conv2.py`、`sim/gen_engine_tb.py`、`S08_Conv2.kicad_sch`、`docs/REPORT_Conv_FC.md`。
- 补丁已在 baseline 副本上验证：`git -c core.autocrlf=false apply m12.patch` 后与 work 中四个文件逐字节一致。

## 14. 主工程应用记录（2026-11-05 后续）

本报告最初记录的是隔离副本验证。主进程已把同一补丁应用到主工程，并同步了主工程 harness 的 `conv2_in()`：

```bash
cd D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System
patch -p1 --binary < output/model_reviews/repair_m12/m12.patch
python tools/build_top.py        # 替换 S08 的 __ROOT_UUID__ 并更新层次实例路径
kicad-cli sch export netlist --format kicadsexpr -o output/top.net CNN_74xx_System.kicad_sch
python tools/audit_top_connectivity.py output/top.net
python sim/run_all.py
python output/model_reviews/muse-slot-session-model/harness_datapath_layout.py
kicad-cli sch erc --severity-all -o output/top-erc-after-m12.rpt CNN_74xx_System.kicad_sch
```

主工程应用后的证据：

| 检查 | 结果 |
|---|---|
| `output/top.audit.json` | `single_node_module_nets=90`、`unexpanded_bus_nets=27`、`done_541_output_count=1` |
| `output/sim_run_all_after_m12.log` | 9/9 PASS |
| 布局 harness | `RESULT: PASS (0 failures)`，POOL1_OUT→CONV2 7200/7200 |
| `output/top-erc-after-m12.rpt` | 42 errors / 895 warnings / 937 messages |
| S08 PDF/BOM | 已由 `tools/export_review.py` 重新生成 |

因此本报告第 1 节“主工程源文件未修改”已不再适用；补丁现已成为主工程当前状态。主工程 harness 的 `conv2_in()` 已改为 CHW，不再是旧公式。

SHA-256：

```text
02a96a38dff1cfccfc2ac777e224022624c61cc4a86f4bce1e594b73bde0a6ab  tools/build_conv2.py
f725d75a9fed157c6ea9d34136daf80af91cd4d7098e2522706a1f00d65340a9  sim/gen_engine_tb.py
242f723211baf80046f4843ce4c66a1352189b10c205117229eda7e74867fdc7  S08_Conv2.kicad_sch
7edb9e5c13f14342c0d7fc91bb0d35f3b71cbea1cd32b031d92db8644ee9d86f  docs/REPORT_Conv_FC.md
c8a46bd47898ea11a17a01d81a0611015d2ea8aa6e8d4f3a9197f61ba65baa3b  output/top.net
a2b92fc3c6c81baa130885c042da8c0fb638828efa2792c634ea35bc7ae89093  m12.patch
```
