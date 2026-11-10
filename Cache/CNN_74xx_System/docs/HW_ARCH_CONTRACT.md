# CNN 74 系列硬件架构契约（V1.1，工作版）

工程路径：`Cache/CNN_74xx_System`
本文件是图纸、SPICE 仿真和说明手册的共同依据。任何接口/状态编码变更必须先改本文件，再改图。

## 1. 已冻结的工程决策

| 项目 | 决策 |
|---|---|
| 逻辑家族 | 74HC/74HCT 混合，5V。HCT 用于与 TTL/存储器接口的输入，HC 用于内部逻辑。缺失符号用同引脚 74LS 符号派生（74HC161/283/157/08/32）。 |
| 系统时钟 | 单一时钟 `CLK = 8.000 MHz`，占空比 50%。禁止门控时钟和组合时钟。 |
| 复位 | `RESET_N` 低有效；外部异步断言，内部两级同步释放。 |
| 控制实现 | 微码 ROM + 状态寄存器 + 输出寄存器。监督 FSM 使用 2×27C512 组成 16 位微码；局部 FSM 使用 27C512/28C256 + 74HC574/74HCT273。 |
| 乘法 | 8×8 查表：`ADDR={A[7:0],B[7:0]}`；`ROM_LO=(A*B)[7:0]`，`ROM_HI=(A*B)[15:8]`。每个引擎独立一对 27C512。 |
| 累加 | 32 位有符号累加器；`RAW_SUM`、`SUM_X`、`SUM_W` 均 32 位。 |
| Zero-point 校正 | `ACC=RAW_SUM - zp_w*SUM_X - zp_x*SUM_W + N*zp_x*zp_w + bias`；乘法用引擎内串行 32×16 乘法器。 |
| Requant | 串行 32×16→48/64 位乘加，按模型 `M/S` 算术右移、四舍五入、饱和；ReLU 下限为 `zp_out`。 |
| FC2 | 不饱和到 uint8；10 个类别统一到同一 signed32 分数尺度，little-endian 写入。 |
| 特征存储器 | 7× 6264（8K×8），每片独立片选/地址空间：INPUT、CONV1_OUT、POOL1_OUT、CONV2_OUT、POOL2_OUT、FC1_OUT、FC2_LOGITS。 |
| 权重存储器 | 4× 62256（32K×8 SRAM）：CONV1/CONV2/FC1/FC2 各一片。易失，扩展板上电时从 SD 经 J10005 装载。 |
| 偏置存储器 | 无。V2 requant 没有 bias 加法器，原 4 片 28C256 已删除。 |
| qparam 存储器 | 无。V2 requant 每层统一 2^S，原 4 片 28C256 已删除。 |
| LUT ROM | 8× W27C512（64K×8），四对，分别属于四个引擎；编程器烧录，只读。 |
| 微码 ROM | 监督 FSM 2×W27C512；局部 FSM 每个引擎 2×W27C512。 |
| 存储器时序 | 统一 `MEM_IF` 适配器：`nCE/nOE/nWE`，参数化 `WAIT_READ`/`WAIT_WRITE`。 |
| 板级 | 本次交付原理图/网表/BOM/PDF/仿真，不含 PCB。 |

## 2. 监督 FSM 状态编码（5 位）

| 编码 | 状态 | 说明 |
|---:|---|---|
| 0 | G_RESET | 复位后第一拍，清输出，转 G_WAIT_READY |
| 1 | G_WAIT_READY | 等 IMAGE_READY & MODEL_READY |
| 2 | G_IDLE | 等 START；未 ready 时启动则 ERROR |
| 3 | G_C1_START | 发 CONV1 start 脉冲 |
| 4 | G_C1_WAIT | 等 CONV1 done |
| 5 | G_P1_START | 发 POOL1 start |
| 6 | G_P1_WAIT | 等 POOL1 done |
| 7 | G_C2_START | 发 CONV2 start |
| 8 | G_C2_WAIT | 等 CONV2 done |
| 9 | G_P2_START | 发 POOL2 start |
| 10 | G_P2_WAIT | 等 POOL2 done |
| 11 | G_FC1_START | 发 FC1 start |
| 12 | G_FC1_WAIT | 等 FC1 done |
| 13 | G_FC2_START | 发 FC2 start |
| 14 | G_FC2_WAIT | 等 FC2 done |
| 15 | G_ARGMAX_START | 发 ARGMAX start |
| 16 | G_ARGMAX_WAIT | 等 ARGMAX done |
| 17 | G_FINISH | 锁存 RESULT，DONE 一拍，RESULT_VALID=1 |
| 18 | G_WAIT_START_LOW | 等 START 撤销 |
| 19 | G_ERROR | 锁存 ERROR，停止下游 |

### 2.1 微码地址（16 位）

`A[4:0]=state[4:0]`

`A5=START_SYNC`, `A6=IMAGE_READY_SYNC`, `A7=MODEL_READY_SYNC`,
`A8=C1_DONE`, `A9=P1_DONE`, `A10=C2_DONE`, `A11=P2_DONE`,
`A12=FC1_DONE`, `A13=FC2_DONE`, `A14=ARGMAX_DONE`, `A15=TIMEOUT`

### 2.2 微码数据（16 位）

| 位 | 名称 | 说明 |
|---:|---|---|
| 4:0 | NEXT_STATE | 下一状态 |
| 5 | BUSY | 系统忙 |
| 6 | DONE | 完成脉冲（仅 G_FINISH 为 1） |
| 7 | RESULT_VALID_SET | G_FINISH 置位 RESULT_VALID DFF |
| 8 | ERROR | 错误锁存 |
| 11:9 | STAGE_CODE | 0=无，1=C1，2=P1，3=C2，4=P2，5=FC1，6=FC2，7=ARGMAX |
| 12 | TIMEOUT_CLR | 清 24 位超时计数器 |
| 15:13 | SPARE | 预留；当前置 0 |

`STAGE_CODE` 由 74HC238 译码为 7 路 start 脉冲。`TIMEOUT_CLR` 在每个 `*_START` 状态有效，实现逐阶段超时。

### 2.3 关键迁移

- G_RESET → G_WAIT_READY 无条件。
- G_WAIT_READY：`ready=IMAGE_READY&MODEL_READY`；ready→G_IDLE。
- G_IDLE：`START & ready`→G_C1_START，BUSY=1；`START & !ready`→G_ERROR；否则保持。
- 每个 `*_START`：对应 STAGE_CODE，下一拍进入 `*_WAIT`。
- 每个 `*_WAIT`：对应 done→下一 START；`TIMEOUT`→G_ERROR；否则保持。
- G_FINISH：DONE=1，RESULT_VALID_SET=1，BUSY=0；→G_WAIT_START_LOW。
- G_WAIT_START_LOW：START=0→G_IDLE；否则保持。
- 任意 WAIT 的 TIMEOUT→G_ERROR；G_ERROR 保持到 RESET。

## 3. 存储器时序控制器

状态：`T_IDLE → T_SETUP → T_WAIT(n) → T_CAPTURE → T_HOLD → T_RELEASE → T_DONE`。

- 读：`ADDR` 建立后拉低 `nCE/nOE`；等待 `WAIT_READ` 拍；在 `T_CAPTURE` 的 CLK 边沿锁存数据；随后 `nOE` 拉高、`nCE` 拉高。
- 写：`ADDR/DATA` 建立后拉低 `nCE/nWE`；保持 `WAIT_WRITE` 拍；先撤 `nWE`，再撤 `nCE`；`T_DONE` 必须在最后一个 hold 周期之后。
- `WAIT_READ = ceil((max(tAA,tCE,tOE)+margin)/Tclk)`；`WAIT_WRITE = ceil((tWP+tDH+margin)/Tclk)`。
- 默认：SRAM `WAIT_READ=2`、`WAIT_WRITE=2`；EEPROM `WAIT_READ=3`；LUT ROM `WAIT_READ=2`。所有值可参数化。

## 4. 模块层次图清单

| 图号 | 文件 | 内容 | 主要器件 |
|---|---|---|---|
| S00 | `CNN_74xx_System.kicad_sch` | 顶层 | 层次图、连接器、测试点 |
| S01 | `S01_Supervisor.kicad_sch` | 监督 FSM、超时、状态输出 | 2×27C512、74HCT273、74HCT574、74HC238、74HC157、74HC161、74HC688、74HC74、74HCT541 |
| S02 | `S02_Timing.kicad_sch` | 存储时序控制器 | 27C512、74HCT574、74HC161、74HC688、74HC157、74HCT541 |
| S03 | `S03_LUT_Mult.kicad_sch` | 8×8 LUT 乘法单元（4 实例） | 2×27C512、4×74HCT574 |
| S04 | `S04_Memories.kicad_sch` | 7×6264 + 4×28C256 权重 + 4×28C256 偏置 + 4×28C256 qparam | 6264、28C256、74HC138、74HC245 |
| S05 | `S05_Pool.kicad_sch` | POOL1/POOL2 | 74HC161、74HC157、74HC85、74HCT574 |
| S06 | `S06_Argmax.kicad_sch` | 10×signed32 比较 | 74HC161、74HCT574、74HC85、74HC688 |
| S07 | `S07_Conv1.kicad_sch` | CONV1 地址/控制/累加/requant | 74HC161、74HC283、74HCT574、74HC85、27C512 |
| S08 | `S08_Conv2.kicad_sch` | CONV2 同上 | 同上 |
| S09 | `S09_FC.kicad_sch` | FC1/FC2 | 同上 + signed32 输出 |
| S10 | `S10_Top_IO.kicad_sch` | 加载接口、连接器、复位/时钟 | 74HCT245、74HCT541、74HC04 |

## 5. 仿真约定

- 引擎：KiCad 10 自带 `ngspice.dll`（shared API），由 `tools/ngspice_runner.py` 驱动。
- 模型：数字功能用 XSPICE `d_dff` + `B` 源组合逻辑；存储器用行为级 `B` 源/查找表；模拟时序用 RC/门延迟近似。
- 每个模块一个 `sim/tb_<module>.cir`，带 `.meas` 断言；`sim/run_all.py` 汇总 PASS/FAIL。
- 功能仿真验证状态序列、地址序列、握手、读写时序、算术边界；不替代晶体管级电气仿真。
- 所有仿真结果写入 `output/sim/<module>.log`，PDF 写入 `output/pdf/<module>.pdf`。

## 6. 验收

- 每张图 ERC 0 error；warning 有书面理由。
- 网表可导出；BOM 位号唯一。
- 每个模块 SPICE 仿真 PASS，日志可复现。
- 顶层状态序列与规划书 5 节一致；时序控制器 done 晚于最后一次写。
- PDF 可读，含接口表、状态表、时序图说明。
