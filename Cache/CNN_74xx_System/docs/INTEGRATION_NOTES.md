# 顶层集成与评审产物说明（V3）

日期：2026-11-07  
范围：把 12 张板卡（32 张图页）挂入 S00，统一位号/电源/状态命名，生成 ERC、BOM、PDF 与评审包。

## 1. 层次结构与位号

- S00 根图实例化 **32 张图页、12 个板卡框**（B01–B12）。每个框内是该板的
  模块图和 `Bxx_Conn` 背板连接器页。
- 板卡：B01 S01、B02 S02、B03 S04、B04 S07+S13、B05 S05_Pool1+S12A_PoolLatch1、
  B06 S08+S15、B07 S05_Pool2+S12A_PoolLatch2、B08 S09_FC1+S17_FC1、
  B09 S09_FC2+S17_FC2、B10 S06+S12B_ScoreLatch、B11 S11+S11A_EngineMerge、
  B12 S10。
- `S14_ParamLoader`、`S16_ParamLoader_C2`、`S18_ParamLoader_FC` 已删除；S13/S15/S17 不再有参数口。
- `S_LUT_Mult_1` 作为单元参考单独出 PDF，不挂入顶层；V3 起 S07–S09 不再实例化该块，改为每引擎 8 片 27C512。
- 每张子图使用独立位号块：
  - S01 1000、S02 2000、S04 4000、S05_Pool1 5000、S05_Pool2 5100、
    S06 6000、S07 7000、S08 8000、S09_FC1 9000、S09_FC2 9200、
    S10 10000、LUT 11000、S11 12000、S11A 12500、S12A_PoolLatch1 13000、
    S12A_PoolLatch2 13100、S12B 13200、S13 14000、S15 15000、
    S17_FC1 16000、S17_FC2 16200、B01–B12 连接器 20000–21100。
  - 例：S07 的 U5 为 U7005；S09_FC1 从 U9001 起；S17_FC2 从 U16201 起；
    B03 的排针为 J20201..J20208。
- 子图符号实例路径统一为 `/<root_uuid>/<sheet_uuid>`。
- `tools/renumber_refs.py`、`tools/build_top.py` 可重复执行。

## 2. 电源与状态

- 全层次只保留 S00 的一对 `PWR_FLAG`（+5V/GND）；子图的重复 PWR_FLAG 由 `tools/strip_pwr_flags.py` 删除。单独打开子图时会出现 `power_pin_not_driven`，属预期。
- 阶段 done 链：
  - S05：`POOL_DONE` 经 U41 分成 `P1_DONE = POOL_DONE & ~POOL_SEL`、`P2_DONE = POOL_DONE & POOL_SEL`。
  - S06：`ARGMAX_DONE`、`ARGMAX_BUSY`、`ARGMAX_RESULT_VALID`。
  - S07：`C1_DONE`、`C1_BUSY`；Requant 状态为 `C1_REQ_QSTB/SAT_FLAG/REQ_BUSY/REQ_DONE`。
  - S08：`C2_DONE`、`C2_BUSY`；Requant 状态为 `C2_REQ_*`。
  - S09_FC1：`FC1_DONE`；S09_FC2：`FC2_DONE`；Requant 状态为
    `FC1_REQ_*` / `FC2_REQ_*`，各由同板 S17_FC1/S17_FC2 返回。
  - 每份引擎变体把不用的 `P2_START`/`P1_START`、`FC2_START`/`FC1_START`
    和 `POOL_SEL`/`FC_SEL` 固定接 GND/+5V；未用的 DONE 输出改成 `*_NC`
    单节点标签，避免两份变体同时驱动同一网络。
- S05 的 `P1_START/P2_START` 经 U42A 74HC32 合成页内 `POOL_START`；S06 直接使用 `ARGMAX_START`。S01 是唯一阶段调度源。
- S06 的结果寄存器输出为 `RESULT_IN0..3`，进入 S01 的 U10 结果锁存；S01 输出 `RESULT0..3` 给主机。
- S13/S15 通过全局标签与 S07/S08 的 `C1_*`/`C2_*` 引擎网相连；S17 与 S09 的 `FC_*` 相连。

## 3. V2 Requant 接口

| 核心 | 输入 | 输出 | 规模 |
|---|---|---|---|
| S13 (C1) | `C1_ACC[31:0]`, `C1_REQ_START`, CLK, RESET_N | `C1_REQ_Q[7:0]`, `C1_REQ_QSTB`, `C1_SAT_FLAG`, `C1_REQ_BUSY`, `C1_REQ_DONE` | 13 DIP |
| S15 (C2) | `C2_ACC[31:0]`, `C2_REQ_START` | `C2_REQ_*` | 13 DIP |
| S17 (FC) | `FC_ACC[31:0]`, `FC_REQ_START`, `FC_SEL` | `FC_REQ_Q[7:0]`, `FC_REQ_QSTB`, `FC_SAT_FLAG`, `FC_REQ_BUSY`, `FC_REQ_DONE` | 24 DIP |

- Conv/FC1：`Q = clamp(ACC >> S, 0, 255)`；`S` 分别为 8/9/8。
- FC2：不做 requant，`FC_REQ_Q` 是原始 signed32 ACC 的 4 个字节（小端），由 `BC[1:0]` 选择。
- 没有 `M/ZP/BIAS/PDATA/PSEL/PLOAD/MODE/RELU_EN`；模型必须零 bias、每层统一 2^S。
- 详细说明：`docs/REQUANT_SIMPLE_V2.md`。

## 4. 时序默认值

S02 的 U7 等待值选择器默认接：

- `WAIT_READ = 3`（覆盖 28C256 读）；
- `WAIT_WRITE = 2`（6264 写）。

原来的 4 位全局 `WAIT_READ/WRITE` 在系统集成时由这组默认值取代；需要按器件动态配置时，把这四个输入改接 S10 的 DIP 开关或配置锁存器。

V2 Requant 的转换延迟很短：

- Conv1/Conv2：START → QSTB 1 CLK → DONE 2 CLK；
- FC1：BC=0 时 QSTB/DONE；
- FC2：BC=0..3 时 QSTB，BC=3 时 DONE。

在 8 MHz 下是亚微秒级；10–100 Hz 的整系统时序仍未重算（M-10）。

## 5. 顶层 ERC 当前状态

`kicad-cli sch erc CNN_74xx_System.kicad_sch`（2026-11-07，V3 集成后）：

```
发现 1407 条违规项
errors 0 / warnings 1407
```

S12A/S12B 已消除 Pool/Argmax 的数据输入 error；S13/S15/S17 的输入由
S07/S08/S09_FC1/S09_FC2 的板内 ACC 驱动。剩余 warning 主要是 74HC 别名符号库一致性、单页全局标签、未用备用门和测试点。

| 网络/功能 | 处理 |
|---|---|
| `IN_DATA1/2[7:0]` | S12A_PoolLatch1/2 各 1 片 74HCT541 从 `DATA[7:0]` 缓冲，板内使用 |
| `SCORE_DATA[31:0]` | S12B U1–U4 4×74HCT574 字节锁存；U5 74HC238 用 `SCORE_ADDR[1:0]`/`MEM_ACK` 译码 |
| `SCORE_ADDR[5:0]` | S06 U38 输出 `{CLASS,BYTE}=class*4+byte`，U39 为 2 位字节计数器 |
| S04 地址 | C1/C2 由 U44–U47、FC1 由 U48/U49、FC2 由 U58/U59、Argmax 由 U50/U51、POOL1 由 U52–U56、POOL2 由 U60–U64 三方态合并到 `ADDR[15:0]`；低 16 位地址不经过 S11 |
| S11 主控 | Argmax 为 master 4；Pool 为 master 5；27C512 A7=MASTER2、A8=POOL_SEL；S11 本体不区分 FC1/FC2、POOL1/POOL2 |
| S11A 合并 | `FC2_BUSY`/`POOL2_BUSY` 选择 157，把 FC1/FC2、POOL1/POOL2 的 region/REQ/WE/BUSY 接回 S11 单一槽位 |
| S13/S15/S17 | 无参数口；Q/QSTB/SAT/BUSY/DONE 直接跨页 |
| S09 字节计数 | `FC_REQ_QSTB` 直接接 74HC161 的 CEP/CET；FC2 的 4 个 QSTB 使 BYTE=0..3，地址 `neuron*4+byte` |

顶层审计：**0 个未展开总线 / 1 个 DONE 驱动**。`POOL_BUSY` 已接入 S11；板内单节点网只有 `ARGMAX_RESULT_VALID`（S06 测试点）和 `OUT_WE`（S05 预留，变体中改名为 `POOL1/2_OUT_WE_NC`）。

## 5.1 V3 A/B 分流与 LUT 展开

- S07/S08/S09 的 A/B 不再同接 `DATA`：`A_LAT`/`B_LAT` 两片 574 分别在
  `A_LOAD`/`B_LOAD` 捕获 S02 读回字节；`SHIFT_EN` 一次把两路同时移入
  4 级流水线。每级 2:1 保持 mux（16×74HC157/引擎）在等待态冻结流水线。
- 本地 FSM 由 11 状态扩为 13 状态：`E_WAIT_A`、`E_WAIT_B`、`E_SHIFT`、
  `E_ACC`；`MEM_DONE` 进入 ROM 地址 A8，写完成不再靠固定延时。
- 微码镜像：`model/microcode/c1_rom1.bin`、`c1_rom2.bin`、`c2_*`、`fc_*`
  （各 64K×8）；生成器 `tools/gen_engine_microcode.py` 带分支自检。
- CONV1 25 MAC 通过 3 个零 B MAC 补齐到 28，`PAD_ACTIVE` 驱动 B 锁存
  前的 2×74HC157 零 mux；权重布局保持 `oc*25+ky*5+kx` 不变。
- 累加器改为 4×74HCT273（异步 `~MR`），删除 32 个 10 k 下拉；避免
  旧 574 三态方案在 `ACC_CLR` 撤销后把旧值重新加回。
- 24 片独立 27C512：每引擎 4 lane ×（低/高字节）。地址
  `A[15:8]=A`、`A[7:0]=B`；`LUT_AB_LATCH`/`LUT_PROD_LATCH` 不再使用。
- 验证：`sim/harness_ab_path.py` 81 项结构检查 + 随机等待态流水线/
  4-MAC 分组模型；`sim/run_all.py` 13/13 PASS。
- 已知限制：FC2 的 4 字节写回仍只有一个 OUTHOLD 字节寄存器，需在
  流片前增加 4×574 暂存 + 4 个写状态；不影响 FC1/CONV/Argmax。

## 5.2 12 板卡与背板（方案 A）

- 12 张板卡、32 张图页；每板含一个 `Bxx_Conn` 连接器页。
- 共 **32 片 2x20P**、1280 脚；统一电源脚：1–4 `+5V`、5–8 `+3V3`
  （预留）、9–14 `GND`；15–40 为信号，每片 26 个。
- 排针数：B01 2、B02 1、B03 8、B04 2、B05 3、B06 2、B07 3、B08 2、
  B09 2、B10 1、B11 3、B12 3。
- 跨板网络 **282 个**（+5V/+3V3/GND 另计）；板内网络不上底板。
- 生成器：`tools/build_boards.py`（按“同一网络出现在两块以上板卡”自动
  计算外部网表）、`tools/backplane.py`、`tools/gen_backplane_csv.py`。
- 最终引脚表：`output/backplane/backplane_pinout.csv`；逐网视图：
  `output/boards/backplane_nets.csv`；板卡清单：
  `output/boards/BOARD_MANIFEST.csv`。
- 顶层 ERC 0 error / 1407 warning；BOM 1329 件 / 896 DIP / 32 BACKPLANE。

## 6. BOM

`output/bom/CNN_74xx_System_BOM.csv`：

- 总数量 **1329**：**896 片 DIP IC/存储器** + 32 片 2x20P 背板排针 +
  连接器/测试点/电容等无源件。
- S07 143、S08 144、S09_FC1 132、S09_FC2 132、S11 14、S11A 5、S04 64、
  S05_Pool1/2 各 45、S06 45、S13 13、S15 13、S17_FC1/2 各 24 片 DIP。
- S07/S08/S09 每引擎新增 8×27C512（LUT）+ 2×27C512（本地微码）+ 16×74HC157（保持 mux）+ 2×74HCT574（A/B 锁存）+ 1×74HC74（POINT_LAST 打拍）；累加器由 4×74HCT574 改为 4×74HCT273，并删除 32 个 10 k 下拉/引擎。
- S13/S15 每核心：4×74HC157、1×74HCT574、1×74HC74、5×74HC32、1×74HC08、1×74HC04。
- S17：13×74HC157、1×74HCT574、1×74HC161、1×74HC74、5×74HC32、2×74HC08、1×74HC04。
- 剩余无封装块符号 **0** 个：`LUT_Mult_Unit` 已全部展开为 24 片独立 27C512；S09 `Requant_Block` 已删除。
- 其余 74HC/HCT、6264、28C256、27C512、连接器、电阻/电容均有封装。

## 7. 复现顺序

```bash
cd Cache/CNN_74xx_System
python tools/build_all.py          # 13 个模块/模板 + variants + flags + boards + renumber + top
python tools/export_review.py --no-preview
python sim/run_all.py
python tools/md_to_pdf.py docs/HW_MANUAL.md -o output/pdf/HW_MANUAL.pdf
python tools/build_review_pdf.py
```

`build_all.py` 的顺序固定为：模块图（S05/S09/S17 写入 `templates/`）→
`make_variants.py`（6 份固定变体）→ `strip_pwr_flags.py` →
`build_boards.py`（12 张连接器图 + 清单）→ `renumber_refs.py` →
`build_top.py`。旧版合并 S12 与共享引擎图已移入 `legacy/`，不参与构建。

## 8. 2026-11-06 V2 变更

已应用：
- 删除 S13/S15/S17 通用门级核心（32×16 乘法器、49 位修正、2×27C512 微程序）。
- 删除 S14/S16/S18 参数装载器；根图、位号、BOM、PDF 全部移除。
- S13/S15 改为 13 片固定移位钳位核心；S17 改为 24 片 FC1/FC2 核心。
- S07/S08/S09 删除 `Cx_A3/B3`、`MAC_EN/ACC_CLR`、`MODE/RELU_EN`、`FC_PDATA/PSEL/PLOAD` 全局接口。
- 新增 `sim/gen_requant_simple_tb.py`；`sim/run_all.py` 11/11。
- 顶层 ERC 0 errors / 940 warnings；BOM 1011 件 / 576 DIP / 12 LUT 块。
- 旧版完整核心归档到 `Cache/_archive_requant_full/`。

下一步：
- LUT 展开（M-08/M-11）：12 个 `LUT_Mult_Unit` → 4 条物理 lane/8 片 27C512 的映射与 BOM。
- 10–100 Hz 时序重算（M-10）与 S02 未用译码输出清理（M-13）。
- S09 本地 FSM 微码镜像导出与逐状态仿真。
- 28×28 模型重训/导出，满足 V2 零 bias、统一 2^S 契约。
