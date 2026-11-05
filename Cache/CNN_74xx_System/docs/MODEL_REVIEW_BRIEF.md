# 独立模型联合审查 Brief

日期：2026-11-05
工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`
规划书：`D:/Document/tempPrj/74Series-CNN/CNN_74xx_MNIST_28x28_v1.txt`
备份：`D:/Document/tempPrj/74Series-CNN/Cache/_backup_CNN_74xx_System_20261105`

## 1. 目标

对 74 系列 MNIST CNN 硬件工程做一次**独立、对抗性**的 SPICE 功能验证和跨模块联合逻辑审查，尽量在制板前发现会导致一次成功率下降的问题。不要把已有文档当作正确性证明；必须自己运行、自己检查、自己给证据。

## 2. 系统拓扑

- 28×28 单通道 MNIST 图像。
- CONV1：5×5、8 通道；POOL1：2×2/stride 2；CONV2：3×3、16 通道；POOL2：2×2/stride 2；FC1：400→32；FC2：32→10；ARGMAX。
- 数据通路：8 位数据总线、32 位累加器、LUT 乘法、零点修正/requant/ReLU。
- S01 Supervisor：20 状态微码 FSM，2×27C512 微码，74HCT273 状态寄存器，74HCT574 输出寄存器，24 位超时计数器。
- S02 Timing：存储时序控制器，nCE/nOE/nWE 低有效，WAIT_READ/WAIT_WRITE，ACK/DONE/BUSY。
- S04 Memories：7×6264 特征 SRAM，12×28C256 权重/偏置/qparam，8×27C512 LUT ROM，24 位地址 + MEM_SEL 64 KB 窗口。
- S05 Pool、S06 Argmax、S07 Conv1、S08 Conv2、S09 FC、S10 Top IO。
- 当前图纸使用全局标签互连；根图是 S00 总览 + 模块连接表。

## 3. 当前已完成的验证（不能直接当作你的结论）

- `python sim/run_all.py` 的历史结果：9/9 checks passed。
- 顶层 ERC 历史上报 42 errors / 898 warnings；无 pin-to-pin、不同网络同网、输出短路。
- BOM 可采购 IC 约 490 片（另有 1 片 8 MHz 晶振）；18 个未展开块符号。
- 最新修改：修复 S07–S09 字段/标签/块符号错位；新增 S00 根图连接总表和 `output/connection_matrix.csv`。
- 历史仿真证据：`sim/*.log`、`output/sim/*.log`、`output/pdf/*.pdf`、`output/erc/*.rpt`。

## 4. 已知的候选缺口（必须独立核实，不要盲信）

1. 12 个 `LUT_Mult_Unit` 块符号可能只是 4 个共享 LUT lane 的逻辑视图；S04 的 8 片 27C512 才是物理 LUT 表。
2. S02 只有一份共享时序控制器；S07–S09 的 3 个 `S02_MEM_IF` 是页内占位符。其 `REQ/WE` 是否有外部驱动、`ACK/DONE/BUSY` 是否回送引擎，需要核实。
3. S07–S09 的 `Cx_ADDR`、`Cx_MEM_nCE` 是否真正接到 S04 的 `ADDR/MEM_SEL`？如果没接，联合逻辑是不完整的。
4. V2 Requant 是固定移位钳位（S13/S15/S17）；检查 `clamp(ACC>>S,0,255)`、FC2 四字节、零 bias/统一 scale 契约是否与模型一致。
5. 顶层仍有 42 个 `pin_not_driven` 错误；判断哪些是外部接口，哪些是真正的内部断链。
6. 时钟实际可能 10–100 Hz 可调；按 8 MHz 写的等待状态/超时是否需要重算？单步/慢时钟下是否有握手宽度问题？
7. 共享 LUT/S02 与“每引擎独立”之间的文档矛盾；BOM 的 490 片与 18 个块符号的口径。

## 5. 必须执行的工作

### 5.1 建立隔离副本

不要修改主工程。把工程复制到自己的目录（建议 `D:/Document/tempPrj/74Series-CNN/Cache/_review_<slug>/work`），在副本里运行。报告写到主工程的 `output/model_reviews/<slug>/`。

### 5.2 跑现有 SPICE/功能测试

在副本根目录运行：

```bash
python sim/run_all.py
```

并至少抽查/重跑：

```bash
python tools/gen_lut.py
python sim/gen_lut_tb.py
python sim/gen_glue_tb.py
python sim/gen_supervisor_tb.py
python sim/gen_timing_tb.py
python sim/gen_mem_decode_tb.py
python sim/gen_pool_tb.py
python sim/gen_argmax_tb.py
python sim/gen_engine_tb.py
```

记录每条命令的 exit code、耗时、PASS/FAIL、日志路径。不要只贴最后一行；关键断言要看日志。

### 5.3 联合逻辑验证（至少选两种，鼓励都做）

A. **FSM→引擎→存储握手**：用 SPICE 或行为级测试驱动 S01 状态序列，检查 C1/P1/C2/P2/FC1/FC2/ARGMAX 的 START 与对应 DONE 握手、超时分支、RESULT_VALID 粘滞、G_WAIT_START_LOW。
B. **S02↔S04 存储事务**：检查读/写状态序列、nCE/nOE/nWE 互斥、WAIT 计数、ACK/DONE 位置、地址/MEM_SEL 译码、64 KB 窗口。
C. **引擎地址/数据序列**：Conv1/Conv2/FC 的 MAC 数、地址序列、累加器写回、Pool/Argmax 边界。
D. **静态网表联合审计**：用 `kicad-cli sch export netlist` 导出顶层网表，检查多驱动、未驱动、同名不同网、引擎到 S04/S02 的断链、全局标签孤岛。给出具体网络名/引脚坐标。
E. **数据通路一致性**：用小的端到端行为模型（Python 或 SPICE）验证一层 Conv→Pool→FC→Argmax 的数值/地址约定；不要只验证单个模块。

如果现有 testbench 不能覆盖联合路径，请自己写一个最小 harness，放在你的副本/报告目录；不要改主工程源码。

### 5.4 图纸/ERC/BOM 审查

- 用 `kicad-cli sch erc --severity-all` 导出顶层和关键子页 ERC；区分外部输入未驱动、电源标志、库不匹配、真正的短路/多驱动。
- 检查极性：74HC688 `P=R` 低有效、74HC138 输出/使能低有效、nCE/nOE/nWE、RESULT_VALID 锁存、START/DONE 单拍。
- 检查时钟/复位/同步、10–100 Hz 与 8 MHz 下的脉宽和等待计数。
- 检查 BOM 的 490 片口径、位号唯一性、未展开块、去耦电容、封装空值。
- 检查最新 S00 表和 `output/connection_matrix.csv` 是否与实际网络一致。

## 6. 交付物

在你的报告目录写：

1. `REPORT.md`：
   - 模型/环境/命令/耗时
   - 拓扑理解（用自己的话）
   - 每个测试的 PASS/FAIL 和证据
   - 联合逻辑验证结果
   - 发现的问题（按严重度）
   - 与现有文档/结论的冲突
   - 你认为制板前必须修的事项
   - 不确定/未能验证的事项
2. `findings.json`：数组，每项字段：
   `id, severity, module, title, claim, evidence, proposed_fix, confidence, functional`
   severity 取值：blocker/critical/major/minor/info。
3. `commands.log`：实际执行的命令和退出码。
4. 可选：你自己写的 testbench、波形、截图。

**不要修改主工程源码或主工程 .kicad_sch；不要修改备份。** 只允许在副本和报告目录写文件。

## 7. 评审口径

- “PASS”只说明该测试覆盖的断言通过，不等于系统正确。
- 重点找：断链、多个驱动、时序竞争、极性错误、地址/窗口错位、位宽/符号扩展、复位/初值、慢时钟握手、BOM 不可制造。
- 对每个问题给可复现证据；不能复现的写“未证实”，不要编造。
- 不要因为已有 PDF/报告说“通过”就跳过验证。
