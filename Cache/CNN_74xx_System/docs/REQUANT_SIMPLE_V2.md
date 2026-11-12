# V2 简洁 Requant 说明（S13 / S15 / S17）

日期：2026-11-06  
适用：`S13_Requant_C1.kicad_sch`、`S15_Requant_C2.kicad_sch`、`S17_Requant_FC.kicad_sch`

## 1. 为什么改成 V2

旧版把 `Requant_Block` 展开成通用门级核心：32×16 串行乘法器、49 位零点修正、
64 位乘积、串行移位/舍入/粘滞、2×27C512 微程序，再加 S14/S16/S18 三个参数
装载器。结果是 S13/S15 各 429 片、S17 510 片，三块合计 1368 片；原理图已经
无法通过阅读理解，且参数口写时序也没有板级验证。

V2 改成“训练时就把缩放固定下来”的定点数据通路：

```text
Conv1 / Conv2 / FC1:
    Q = clamp(ACC >>> S, 0, 255)
FC2:
    Q[7:0] = ACC[8*byte +: 8]      byte = 0..3，小端
```

没有乘法器、没有零点、没有 bias 加法器、没有参数装载器。S13/S15 各 13 片，
S17 24 片，三块合计 50 片。

## 2. 量化契约（必须与训练/导出脚本一致）

| 项目 | V2 约定 |
|---|---|
| 量化方式 | 对称、无零点：`ZP_X = ZP_W = ZP_OUT = 0` |
| bias | **训练时必须为 0**；V2 没有 bias 加法器 |
| 每层缩放 | 一个固定的 2 的幂：`scale = 2^-S`，同一层所有通道共用 |
| Conv1 | `S = 9`，`Q = clamp(ACC >> 9, 0, 255)` |
| Conv2 | `S = 10`，`Q = clamp(ACC >> 10, 0, 255)` |
| FC1 | `S = 9`，`Q = clamp(ACC >> 9, 0, 255)` |
| FC2 | 不做 requant；原始 signed 32 位 `ACC` 按小端 4 字节送给 Argmax |
| 饱和 | 正溢出 `255`；负数 `0`；`SAT_FLAG` 同时置 1 |
| 舍入 | 直接算术右移，不四舍五入 |

> **重要限制**：如果模型有非零 bias，或每通道需要不同 scale，V2 不适用。
> 必须在训练/导出阶段把 bias 训成 0，并把每层所有通道统一到同一个 2^S。
> 这是用精度换可读性和芯片数；不是通用量化器。

`S` 是构建常量，定义在 `tools/build_requant_simple.py` 的 `SHIFT` 字典：

```python
SHIFT = {"C1": 9, "C2": 10, "FC1": 9}
```

改缩放必须同时改训练导出的 qparam，然后重新运行该构建脚本；原理图上没有
运行时可写寄存器。

### 2.1 移位必须按最终权重标定（打板前必做）

`S` 不是随便取的：它由“权重标定出来的累加器满量程”决定。
同一份权重用错一位，结果不是掉几个点，而是直接失效。

实测（`FPGA_CNN/eval_v2_quant.py`，10,000 张 MNIST 测试图，
per-tensor 对称 int8、零 bias、截断）：

| 移位 | 准确率 |
|---|---:|
| 8 / 9 / 8（旧接线） | **25.64 %** |
| 9 / 10 / 9（当前接线） | **97.83 %** |

原因是 `S` 小一位，右移后的值整体翻倍，绝大多数激活值撞到 255 饱和，
信息全丢。**打板前必须用最终权重重新标定**，步骤：

1. 用最终权重跑一遍校准集，记录每层累加器的 `|ACC|max`；
2. `S = floor(log2(|ACC|max / 255))`，三层分别算；
3. 把结果写进 `build_requant_simple.py` 的 `SHIFT`，重新生成 S13/S15/S17；
4. 每块 8 根取位线 `QRAW[i] = ACC[S+i]`，以及 `HIGH = OR(ACC[S+8..31])`，
   都会跟着变；改完要重新核对这三块的连线。

原理图上没有跳线或寄存器可选移位。如果最终权重导致 `S` 再变，
必须改这 8 根线（每块 8 根，三块共 24 根）并重新投板。

## 3. 电路结构

### 3.1 Conv1 / Conv2（S13 / S15，13 片）

```text
ACC[31:0]
  │
  ├─ QRAW[i] = ACC[S+i]（越界取 ACC[31] 符号扩展）
  ├─ HIGH = OR(ACC[S+8 .. 31])
  ├─ SAT_POS = HIGH & ~ACC[31]
  │
  ├─ 第一级 74HC157 ×2：SAT_POS=1 时选 0xFF，否则选 QRAW
  ├─ 第二级 74HC157 ×2：ACC[31]=1 时选 0x00，否则选第一级结果
  └─ 74HCT574：START 上升沿锁存 QVAL -> Cx_REQ_Q[7:0]

START ──> 74HC74 #1 ──> QSTB ──> 74HC74 #2 ──> DONE
BUSY = START | QSTB | DONE
SAT_FLAG = SAT_POS | ACC[31]
```

- 4×74HC157：两级 8 位 2:1 钳位。
- 1×74HCT574：输出字节寄存器。
- 1×74HC74：QSTB/DONE 两拍状态。
- 5×74HC32：HIGH 的 OR 树、SAT_FLAG、BUSY。
- 1×74HC08：SAT_POS。
- 1×74HC04：NEG 反相。

### 3.2 FC1 / FC2（S17，24 片）

FC1 复用上面的 uint8 钳位；FC2 不钳位，直接做 4:1 字节选择：

```text
FC1: Q8 = clamp(ACC >> 8, 0, 255) -> 74HCT574 -> 输出 mux
FC2: byte0 = ACC[7:0]   byte1 = ACC[15:8]
     byte2 = ACC[23:16] byte3 = ACC[31:24]
     BC[1:0] 选字节：0->byte0, 1->byte1, 2->byte2, 3->byte3
```

- 13×74HC157：4 片 FC1 钳位 + 6 片 FC2 字节 mux + 2 片输出 mux + 1 片
  QSTB/DONE 选择。
- 1×74HCT574：FC1 输出寄存器。
- 1×74HC161：3 位字节计数器 BC。
- 1×74HC74：RUN 状态。
- 5×74HC32、2×74HC08、1×74HC04：OR 树、字节译码、RUN 反馈。
- 没有 Q32 加法/取补/双向钳位：FC2 的 ACC 本身就是 signed 32 位。

### 3.3 时序

| 路径 | QSTB | DONE | 说明 |
|---|---|---|---|
| Conv1/Conv2 | START 后 1 个 CLK | START 后 2 个 CLK | 3 拍完成 |
| FC1 | BC=0（START 后第 1 个计数周期） | 同 QSTB | Q8 已在 START 沿锁存 |
| FC2 | BC=0..3 | BC=3 | 每字节一次 QSTB |

S09 的 `FC_REQ_QSTB` 直接驱动输出保持 mux 和字节计数器；FC2 的 4 个 QSTB
对应 `neuron*4+byte` 的 4 个地址。`FC_REQ_BUSY = START | RUN`。

## 4. 被删除的东西

V2 明确删除，不得再出现在 S13/S15/S17：

- `M[31:0]`、`SHIFT[5:0]`、`ZP_X/ZP_W/ZP_OUT`、`N_MACS`、`BIAS`
- `PDATA[31:0]`、`PSEL[2:0]`、`PLOAD`
- `MODE0/MODE1/RELU_EN`
- 32×16 乘法器、64 位乘积、49 位修正累加器
- 2×27C512 微程序、参数装载器 S14/S16/S18

S14/S16/S18 文件已删除；根图不再实例化它们。

## 5. 验证

`sim/gen_requant_simple_tb.py`：

- 每层 5000 组随机 `ACC` 的 golden clamp 检查，另有 0、±1、`255<<S`、
  `256<<S`、`2^31-1`、`-2^31` 等定向向量。
- FC2 四字节小端检查，含正负数和边界。
- Conv START→QSTB→DONE 三拍模型；FC1/FC2 的 BC/QSTB/DONE 序列。
- 结构：S13/S15 13 片、S17 24 片；无 `PDATA/PSEL/PLOAD/MODE/ZP/BIAS`；
  S14/S16/S18 不存在。
- 顶层网表：`C1_ACC8`、`C2_ACC9`、`FC_ACC0`、`*_REQ_Q0`、`FC_REQ_QSTB`
  真正跨页连接。
- BOM：总 1011 件，576 片 DIP，12 个 `LUT_Mult_Unit`，无 `Requant_Block`。
- 顶层 ERC：0 errors / 940 warnings。

`sim/run_all.py`：11/11 checks passed。

## 6. 限制

1. **bias 必须为 0**；非零 bias 需要额外加法器或训练时折叠，V2 不提供。
2. **每层统一 scale**；不支持 per-channel scale。
3. **直接截断，不四舍五入**；精度比旧版 round-half-up 略低。
4. **FC2 原始 signed32 输出**；Argmax 只要求 10 类同尺度，因此不 requant。
5. 本验证是 golden/结构/网表级，不是 74HC157 门级 SPICE；10–100 Hz 全系统
   时序仍需按实际时钟重新核算（M-10）。
6. 12 个 `LUT_Mult_Unit` 仍是块符号，PCB 前需展开（M-08/M-11）。
