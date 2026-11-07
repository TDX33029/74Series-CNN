# 最终状态与验证矩阵（V2）

日期：2026-11-07  
工程：`Cache/CNN_74xx_System`  
交付：12 张板卡原理图（32 张图页）+ 12 板卡顶层层次图 + 逐板 2x20P 背板连接器、
功能仿真、ERC、BOM、PDF、说明手册。

> **2026-11-07 Option A 板卡化已完成**：原来的 14 张可复用模块图已改为 12 张
> 具体板卡；S05/S09/S17 按层复制为固定变体，S12 拆成两个 Pool 字节缓冲和
> 一个 Argmax 锁存页。板卡清单见 `docs/BOARD_PARTITION.md` 与
> `output/boards/BOARD_MANIFEST.csv`，逐引脚定义见
> `output/backplane/backplane_pinout.csv`。

> V2 已删除通用 Requant 与三个参数装载器。S13/S15/S17 现在是固定移位的
> 小核心；模型契约是 **对称量化、bias=0、每层统一 2^S**。详见
> `docs/REQUANT_SIMPLE_V2.md`。旧版完整门级核心归档在
> `Cache/_archive_requant_full/`，不参与当前构建。

## 1. 逐模块状态

单页 ERC 的 error 只来自“外部输入未驱动 + 电源由 S00 提供”；顶层 0 error。
所有单页均无重复驱动、短路、输出冲突、`different_unit_net` 或悬空输出。

| 图页 | 内容 | 顶层/单页状态 | 功能验证 | DIP IC | PDF |
|---|---|---|---|---|---|
| S01 | 全局监督 FSM、24 位超时、结果锁存 | 单页外部输入 | `PASS: supervisor state sequence`；glue 11/11 | 26 | `S01_Supervisor.pdf` |
| S02 | 存储时序控制器、等待状态 | 单页外部输入 | `PASS: timing controller read/write protocol` | 11 | `S02_Timing.pdf` |
| S04 | 7×6264 + 12×28C256 + 8×27C512 + 地址缓冲 | 单页外部输入 | 片选唯一性 323 checks / 20000 随机向量 PASS | 56 | `S04_Memories.pdf` |
| S05 | POOL1/POOL2 2×2 max（B05/B07 各一份固定变体） | 单页外部输入 | 10 窗口 + 40 地址检查 PASS | 45/份 | `S05_Pool1.pdf`、`S05_Pool2.pdf` |
| S06 | 10 类 signed32 ARGMAX + 2 位字节计数器 | 单页外部输入 | 5 向量（含并列/边界）+ 四字节事务 PASS | 45 | `S06_Argmax.pdf` |
| S07 | CONV1 引擎（A/B 分流 + 8×27C512 LUT） | 顶层 0E | 115200 MAC + 全地址序列 SPICE PASS；A/B 结构 81 checks | 143 | `S07_Conv1.pdf` |
| S08 | CONV2 引擎（A/B 分流 + 8×27C512 LUT） | 顶层 0E | 115200 MAC + 全地址序列 SPICE PASS；CHW | 144 | `S08_Conv2.pdf` |
| S09 | FC1/FC2 引擎（B08/B09 各一份固定变体） | 顶层 0E | 13120 MAC + 72 次写；FC2 四字节 LE | 132/份 | `S09_FC1.pdf`、`S09_FC2.pdf` |
| S10 | 8 MHz 时钟、复位、加载/状态口 | 单页外部输入 | 时钟/复位/缓冲接线审查 | 9 | `S10_Top_IO.pdf` |
| S11 | 总线适配：master/region、27C512 map、REQ/WE | 单页外部输入 | bus map PASS；Pool master 5 | 14 | `S11_BusFabric.pdf` |
| S12A | Pool1/Pool2 字节缓冲（每板 1 片 541） | 单页外部输入 | DATA→IN_DATA1/2 接线检查 | 1/份 | `S12A_PoolLatch1.pdf`、`S12A_PoolLatch2.pdf` |
| S12B | Argmax 四字节锁存 + 238 译码 | 单页外部输入 | 32 结构检查 + 3 向量 PASS | 5 | `S12B_ScoreLatch.pdf` |
| S13 | CONV1 简单 Requant：`clamp(ACC>>8,0,255)` | 顶层 0E | 5000 随机 + 定向 + 握手模型 | 13 | `S13_Requant_C1.pdf` |
| S15 | CONV2 简单 Requant：`clamp(ACC>>9,0,255)` | 顶层 0E | 5000 随机 + 定向 + 握手模型 | 13 | `S15_Requant_C2.pdf` |
| S17 | FC1 `>>8` uint8；FC2 原始 signed32（B08/B09 各一份） | 顶层 0E | 5000 随机 + FC2 字节序 + 握手模型 | 24/份 | `S17_FC1.pdf`、`S17_FC2.pdf` |
| S_LUT | 8×8 LUT 乘法单元 | 块符号 | 65536 地址 errors=0；8 组 SPICE PASS | 6 | `S_LUT_Mult_1.pdf` |
| S00 | 12 板卡顶层层次图（32 张图页 / 12 个板卡框） | **0E / 1407W** | 无结构错误；详见 `INTEGRATION_NOTES.md` | — | `CNN_74xx_System.pdf` |

## 2. 顶层连接与规模

顶层 ERC（`kicad-cli sch erc CNN_74xx_System.kicad_sch`，2026-11-07）：

```
发现 1407 条违规项
errors 0 / warnings 1407
```

- 根图实例化 **32 张图页、12 个板卡框**；每个板卡框内含模块图和该板的
  `Bxx_Conn` 背板连接器页。
- 板卡：B01 监督、B02 时序、B03 存储、B04 CONV1、B05 POOL1、B06 CONV2、
  B07 POOL2、B08 FC1、B09 FC2、B10 ARGMAX、B11 总线适配、B12 主机 I/O。
- 引擎板内：`C1_ACC/C1_REQ_*`（B04）、`C2_ACC/C2_REQ_*`（B06）、
  `FC1_ACC/FC1_REQ_*`（B08）、`FC2_ACC/FC2_REQ_*`（B09）、`IN_DATA1*`（B05）、
  `IN_DATA2*`（B07）、`SCORE_DATA*`（B10）全部为板内网络，不上底板。
- B11 的 S11A 用 `FC2_BUSY` / `POOL2_BUSY` 把 FC1/FC2、POOL1/POOL2 二选一
  送回 S11 原有单一槽位；S11 的 map ROM、master 编码器、REQ/WE 合并未改。
- 底板：12 板共 **32 片 2x20P**、1280 脚；电源脚固定
  1–4 +5V、5–8 +3V3、9–14 GND、15–40 信号。
- 跨板网络 **282 个**（另有 +5V/+3V3/GND 三个电源网）；逐板清单见
  `output/boards/backplane_nets.csv`。
- BOM：**1329 件**；**896 片 DIP IC/存储器**；**0 个 `LUT_Mult_Unit` 块符号**；
  **32 片 2x20P 背板排针**。
- 24 片独立 LUT ROM（S07/S08/S09_FC1/S09_FC2 各 8 片）+ 本地 FSM 微码 ROM。
- Requant 五块合计 **98 片 DIP**（13+13+24+24+24）。

## 3. 仿真

`sim/run_all.py`：**13/13 checks passed**（`output/sim_run_all.log`）。

```
PASS  lut_contents      65536 项，errors=0
PASS  lut_spice         8 组代表操作数
PASS  glue              11/11
PASS  supervisor        0→1→…→18→2
PASS  timing            读/写协议、无 nOE/nWE 冲突
PASS  mem_decode        323 checks / 20000 随机向量
PASS  pool              10 窗口 + 40 地址
PASS  argmax            5 向量（并列/边界）
PASS  argmax_s12        四字节 40 地址/ACK/DONE + S12B 四 lane
PASS  ab_path           A/B 结构 81 checks + 流水线/4-MAC 分组模型
PASS  conv_fc_engines   CONV1/2 115200 MAC，FC 13120 MAC
PASS  requant_simple    5000×3 随机 clamp + FC2 字节序 + 结构/跨页/BOM/ERC
PASS  backplane         32 排针/1280 脚/282 网络逐板核对
```

## 3.1 V3：A/B 分流与 24 片独立 LUT（2026-11-07）

### 3.1.1 A/B 操作数通路（S07/S08/S09 共用模板）

- **输入锁存**：`A_LAT`/`B_LAT` 各 1×74HCT574，D=`DATA[7:0]`，
  Cp=`*_A_LOAD`/`*_B_LOAD`（由 `E_WAIT_A`/`E_WAIT_B` 与 `MEM_ACK` 译码）。
- **保持流水线**：每操作数 4 级 74HCT574，每级 2:1 保持 mux
  （2×74HC157/级，共 16×157/引擎）。`SHIFT_EN=0` 时寄存器保持，
  S02 读等待 3 拍/写等待 2 拍期间流水线不再移位。
- **输入保持 mux**：stage 0 的 I0=自身 Q、I1=`A_LAT`/`B_LAT`，
  S=`SHIFT_EN`；其余级的 I1=前一级 Q。
- **结果**：`PROD = A*B`，不再是 `x*x`；A/B 严格对齐。
- **CONV1 padding**：25 个真实 MAC + 3 个零 B MAC = 28（7 组×4）。
  `PAD_ACTIVE` 把 B 锁存器输入强制为 0；`PAD_LAST` 经 74HC74 打一拍，
  在 `E_ACC` 检查。权重布局不变（不需要把每 oc 25 B 改成 28 B）。

### 3.1.2 本地 FSM（13 状态）

```text
0 E_RESET -> 1 E_IDLE -> 2 E_ADDR_IN -> 3 E_WAIT_A
-> 4 E_ADDR_W -> 5 E_WAIT_B -> 6 E_SHIFT -> 7 E_ACC
-> (POINT_LAST? 8 E_REQ : 2 E_ADDR_IN)
8 E_REQ -> 9 E_ADDR_OUT -> 10 E_WRITE -> 11 E_NEXT
-> (IMAGE_LAST? 12 E_DONE : 2 E_ADDR_IN)
```

- ROM 地址：`A[4:0]=ST`，`A5=START`，`A6=POINT_LAST`，`A7=MEM_ACK`，
  `A8=MEM_DONE`，`A9=REQ_DONE`，`A10=IMAGE_LAST`（S09 另有 `A11=FC_SEL`）。
- ROM1：D[4:0]=next state，D5=BUSY，D6=DONE，D7=`ACC_CLR_N`。
- ROM2：D0=`MAC_EN`，D1=`MEM_REQ`，D2=`MEM_WE`，D3=`OUT_STB`，
  D4/D5=`ADD_SEL`。
- 微码镜像：`model/microcode/{c1,c2,fc}_rom1.bin`、`*_rom2.bin`
  （各 64K×8，`tools/gen_engine_microcode.py` 生成并自检）。
- **累加器**：4×74HCT273 替代 4×74HCT574 + 32 个 10 k 下拉。
  273 的异步 `~MR` 真正清零寄存器，避免旧 574 三态/下拉方案在
  `ACC_CLR` 撤销后把旧值重新放回总线。
- `ACC_LD` 在 `E_ACC` 由 `ACC_EN & LANE_LAST` 产生；lane 计数器在
  第 4 个 `ACC_EN` 同步装 0，保证每 4 个 MAC 只累加一次。

### 3.1.3 LUT 物理展开

- 每个引擎 4 条 lane × 2 片 27C512（低/高字节），共 **24 片**；
  地址 `A[15:8]=A 操作数`、`A[7:0]=B 操作数`，数据
  `低 ROM=PROD[7:0]`、`高 ROM=PROD[15:8]`。
- 流水线 574 的输出直接作为 ROM 地址，保持 mux 保证地址稳定；
  不再需要 `LUT_AB_LATCH`/`LUT_PROD_LATCH` 块内锁存。
- BOM 中 `LUT_Mult_Unit` 块符号为 0；S04 原有的 8 片共享 LUT ROM
  现在为备用（未接入引擎数据通路），保留以便后续降本或复用。

### 3.1.4 验收

- 顶层 ERC：**0 errors / 1407 warnings**（警告均为库符号版本差异、
  未用单元、测试点单端标签）。
- `sim/run_all.py`：**13/13 PASS**，新增 `ab_path` 与 `backplane`：
  - 81 项结构检查：A/B 锁存、保持 mux、LUT 地址/数据、PAD mux、
    FSM ROM 地址位；
  - 行为模型：随机等待态下流水线不动，4-MAC 分组覆盖每个真实 MAC
    恰好一次（CONV1 25+3、CONV2 72、FC1 400、FC2 32）。
- BOM：**1329 件 / 896 DIP**；S07 143、S08 144、S09_FC1 132、S09_FC2 132、S11 14、S11A 5、S04 64、S05 45/份；另有 32 片 2x20P 背板排针。

### 3.1.5 已知限制

- **FC2 四字节输出**：S17 的 `FC_REQ_QSTB` 在 BC=0..3 是 4 拍电平，
  S09 只有一个 OUTHOLD 字节寄存器，因此当前只能写回最后一字节。
  正确做法是增加 4×574 字节暂存 + 4 个写状态（或把 S17 改成 4 个
  单拍 QSTB 并在每个 QSTB 后等 S02 写完成）。该项不影响 FC1、
  CONV1/CONV2 和 Argmax 的现有验证，但 FC2 多字节写回需在流片前补齐。
- S04 的 8 片共享 LUT ROM 目前为备用；若后续要恢复共享 LUT，
  需要重新接回 `*_MEM_nCE_MC` 区域并去掉引擎私有 ROM。

### 3.2 12 板卡划分与背板（2026-11-07，方案 A）

原“14 张可复用模块图 + 40 片排针”方案已被 12 张具体板卡取代。
每块板只做固定功能，层与层之间不再复用一个引擎；板内差异用固定连线和
独立网络前缀实现。

| 板卡 | 名称 | 图页 | 对外网络 | 排针 |
|---|---|---|---|---|
| B01 | SUPERVISOR | S01 | 37 | 2 |
| B02 | TIMING | S02 | 10 | 1 |
| B03 | MEMORY | S04 | 204 | 8 |
| B04 | CONV1 | S07 + S13 | 43 | 2 |
| B05 | POOL1 | S05_Pool1 + S12A_PoolLatch1 | 53 | 3 |
| B06 | CONV2 | S08 + S15 | 43 | 2 |
| B07 | POOL2 | S05_Pool2 + S12A_PoolLatch2 | 53 | 3 |
| B08 | FC1 | S09_FC1 + S17_FC1 | 43 | 2 |
| B09 | FC2 | S09_FC2 + S17_FC2 | 44 | 2 |
| B10 | ARGMAX | S06 + S12B_ScoreLatch | 26 | 1 |
| B11 | BUSFAB | S11 + S11A_EngineMerge | 72 | 3 |
| B12 | HOSTIO | S10 | 59 | 3 |

- 每片排针电源脚一致：**1–4 = +5V，5–8 = +3.3V（预留），9–14 = GND，
  15–40 = 信号（26 个）**。12 板共 **32 片排针 / 1280 脚 / 687 个信号端点**。
- 跨板网络 **282 个**；板内网络（各引擎 ACC/REQ 对、`IN_DATA1/2`、
  `SCORE_DATA`）不上底板。
- `FC_SEL`/`POOL_SEL` 仍由 S01 送 B11 的 map ROM；引擎板把对应选择脚
  固定为 0/1（POOL1/FC1=0，POOL2/FC2=1）。
- B11 的 **S11A_EngineMerge** 用 `FC2_BUSY`/`POOL2_BUSY` 选择
  FC1/FC2 与 POOL1/POOL2 的控制/区域信号，接回 S11 原有单一槽位；
  S11 本体（148 编码器、157 区域 mux、27C512 map ROM、REQ/WE 合并）
  未改动。用 mux 而不是 OR/AND：引擎 138 只由 `MEM_nCE` 限定，空闲引擎
  仍会输出区域码，直接合并会把别的引擎的访问映射到错误窗口。
- B03 的 S04 为 FC2 增加一对地址缓冲（U58/U59，OE=`FC2_BUSY_N`），
  为 POOL2 增加一组 5 片 541 + 1 片 32（U60–U65）；与 FC1/POOL1 组
  一样是三方态合并，靠各自 BUSY/写使能互斥，不额外仲裁。
- 生成链：`tools/build_all.py` → 模块图 → `make_variants.py` →
  `strip_pwr_flags.py` → `build_boards.py` → `renumber_refs.py` →
  `build_top.py`。旧版合并 S12、共享 S05/S09/S17 归档在 `legacy/`。
- 机器可读：`output/boards/BOARD_MANIFEST.csv`、
  `output/boards/backplane_nets.csv`、`output/backplane/backplane_pinout.csv`；
  说明：`docs/BOARD_PARTITION.md`、`docs/CONNECTION_MATRIX.md`。
- 顶层 ERC **0 errors / 1407 warnings**；`sim/run_all.py` **13/13 PASS**；
  BOM **1329 件 / 896 DIP / 32 排针**。
- 历史：40 片排针的旧方案（1060 件 / 681 DIP / 0E 1041W）保留在
  `Cache/_backup_backplane_20261107/`，仅作对照，不再构建。

## 4. 评审产物

- 总评审包：`output/pdf/CNN_74xx_Review_Package.pdf`
- 说明手册：`output/pdf/HW_MANUAL.pdf`
- 系统评审指南：`output/pdf/CNN_74xx_System_Review_Guide.pdf`（28 页，拓扑/端到端流程/微码/流水线/评审发现）
- 模块互联方案：`docs/INTERCONNECT_PLAN.md`；机器可读连接表：`output/interconnect/interconnect_plan.csv`
- 顶层完整层次 PDF：`output/pdf/CNN_74xx_System.pdf`
- 逐图 PDF：`output/pdf/S01…S17`、`S_LUT_Mult_1`
- 逐图 ERC：`output/erc/*.rpt`
- 顶层 ERC：`output/top-erc-simple.rpt`
- 顶层审计：`output/top.audit.json`（2 单节点 / 0 未展开总线）
- BOM：`output/bom/CNN_74xx_System_BOM.csv`（1329 件；896 片 DIP；32 片背板排针）
- 板卡清单：`output/boards/BOARD_MANIFEST.csv`；板卡说明：`docs/BOARD_PARTITION.md`
- 底板逐引脚：`output/backplane/backplane_pinout.csv`
- 微码镜像：`model/microcode/supervisor_lo.bin`、`supervisor_hi.bin`
- 总线映射：`model/busmap/bus_map.bin/.hex/.csv`
- V2 Requant 说明：`docs/REQUANT_SIMPLE_V2.md`
- 生成脚本：`tools/*.py`；仿真脚本：`sim/gen_*_tb.py`
- 旧版归档：`Cache/_archive_requant_full/`（S13–S18 全核、装载器、旧报告）

## 5. 已修复 / 仍限制

已修复：
- **M-01**：Pool/Argmax 的 START 未接 S01；S05 用 U42 合成 `POOL_START`，S06 改用 `ARGMAX_START`。
- **M-02/M-03/M-06**：新增 S11 总线适配层；S02 删除重复 MEM_DATA 245。
- **M-04**：`DONE` 双 74HCT541 驱动；S05 完成信号改名 `POOL_DONE`。
- **M-05/M-09**：S07/S08/S09 删除 `Requant_Block`；V2 用 S13/S15/S17 小核心，删除 S14/S16/S18。
- **M-07**：S12 数据装配 + S06 四字节地址/ACK + S11 Argmax master。
- **M-12**：Conv2 输入地址 HWC→CHW。
- **V2 规模**：Requant 1368 → 50 片；项目 BOM 2845 → 1011 件，DIP 1941 → 576 片。

仍未完成（不能投板）：
1. **M-08/M-11**：12 个 `LUT_Mult_Unit` 仍是块符号，未映射到 8 片 27C512 的物理 lane；封装/去耦未补齐。
2. **M-10**：10–100 Hz 外部时钟与默认等待/超时假设未重算；整幅推理时间会非常长。
3. **M-13**：S02 74HC138 五个状态输出无负载，属低风险冗余。
4. **S09 本地 FSM 微码未导出**：状态/控制位定义在图中，未生成 `.bin`，也没有逐状态仿真。
5. **V2 模型契约**：bias 必须为 0、每层统一 scale、直接截断不舍入；不满足时精度会下降，V2 不会检测。
6. **验证边界**：V2 是 golden/结构/网表级，不是 74HC157 门级 SPICE；门延迟、扇出、时钟 skew、8 MHz 余量未证明。
7. **28×28 模型缺失**：现有训练脚本是 16×16，端到端逐位验证需重新训练/导出 28×28 模型。

## 6. 评审资料

- `output/model_reviews/FINAL_JOINT_REVIEW.md`：五模型/替代证据与逐项判定
- `output/model_reviews/AGREEMENT_MATRIX.md`：一致性矩阵
- `output/model_reviews/MODEL_ASSIGNMENTS.md`：模型可用性
- `output/model_reviews/repair_bus/REPAIR_REPORT.md`：S11 总线修复
- `output/model_reviews/repair_s12/REPAIR_REPORT.md`：S12 数据装配
- `output/model_reviews/repair_argmax4/REPAIR_REPORT.md`：Argmax 四字节事务
- `output/model_reviews/repair_f1f5/REPAIR_REPORT.md`：START/DONE 修复
- `output/model_reviews/repair_m12/REPAIR_REPORT.md`：CHW 地址修复
- `output/model_reviews/iceman-contributor-free/REPORT.md`：Iceman 独立报告
- 旧版 Requant/FC 报告只在 `Cache/_archive_requant_full/reports/` 保留，不再作为当前依据。

## 7. 其他限制

1. S11 的 74HC148 使用 74LS148 符号，实际 BOM 必须采购 74HC148（CMOS）。
2. `LOAD_EN` 与引擎 `BUSY` 没有硬件互锁；推理期间置 `LOAD_EN=1` 会争用地址/片选。
3. 空闲时 `ADDR[15:0]` 浮空；建议加 10k 下拉。
4. 单页 ERC 的电源错误来自“只在 S00 保留 PWR_FLAG”，属预期。
5. FC2 的 10 类必须同尺度；V2 的 `S` 固定，Argmax 只比较原始 ACC，软件不得再对类别做不同缩放。
