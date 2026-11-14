# LED 功能名丝印改造完成报告（2026-11-14）

## 结果

全部 **47 板、1006 颗 LED** 的位号已从默认序号（LED1000 式）改为**按监视信号
派生的功能名**，原理图与 PCB 双侧同步改名，逐板保存完毕。

## 命名规则

```
新位号 = LED_ + 监视信号全名（去掉 /板页/ 前缀；引擎板再去掉 C1_/C2_/FC_ 前缀）
```

示例：
- B04-4：`LED_C1_MAC_EN`（乘法器使能）、`LED_C1_KX_LAST_LO_N`（KX 计数最后
  一拍低电平）、`LED_C1_SP_LAST_HI_N`
- B03-1：`LED_DATA4`、`LED_MEM_NWE_INT`、`LED_READ_DIR`
- B12-1：`LED_MEM_SEL0`、`LED_ERROR_CODE0`
- B05-1：`LED_P1_START`、`LED_POOL1_OUT_DATA6`、`LED_POOL1_MEM_NCE_IN`
- B10-1：`LED_SCORE_DATA10` … `LED_SCORE_DATA15`

长度 6–24 字符；每板内位号唯一（冲突时自动加 _2/_3 后缀；实际 0 冲突）。

## 追溯方法（1006/1006 全部成功，0 颗无法追溯）

对每颗 LED 沿原理图连线图做图遍历：LED 阴极 → Q 集电极 → Q 基极 → 10k
电阻另一端 → 该走线的网络名 = 该 LED 监视的信号。凡监视 GND/+5V/+VLED
或自动名（$N）的不作为信号名（此类为电源指示灯，保留原名或按所属电源
轨命名）。

## 校验

1. **原理图/PCB 位号一致性**：47 板逐一比对——sch=pcb 全部 OK，0 差异。
2. **重名检查**：每板内 LED 新位号无重复。
3. **网表不变**：改名只改 Designator，不动任何导线/网络——B04-4 试点前后
   导线数一致（633），全板器件数一致（116）。
4. **B04-4 试点**：18 颗 bank LED + 2 颗电源 LED 改名后经 EDA 画布截图
   目视确认丝印正确显示（LED_C1_MAC_EN 等）。

## 遗留

- 少数电源指示 LED（如 LEDP1、LED4003/4004 类，监视 +5V/+VLED/GND 的）
  保留原名——它们的功能就是"电源在位"，无信号名可派生。如需也可改名
  （如 LED_PWR_5V、LED_PWR_VLED），数量约 1-3 颗/板，可后续统一处理。

## 数据

- 全工程映射表：`D:/tmp/jlc_brd/state/led_expand/led_names_all.json`
- 改名报告：`state/led_expand/rename_report.json`（每板 done=True）

未提交、未发布、未下单。
