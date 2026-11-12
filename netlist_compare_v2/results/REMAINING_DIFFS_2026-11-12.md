# 74CNN-BRD ↔ CNN_74xx_System 剩余差异清单（已忽略排针问题）

日期：2026-11-12
范围：嘉立创EDA `74CNN-BRD` 全部 47 块板 vs KiCad `Cache\CNN_74xx_System`
说明：背板排针相关差异（封装 40P/64P、电源脚重排、信号重排、EDA 排针无 KiCad 参照、排针多出/悬空脚）全部忽略。本文件**仅列差异**，连接一致的内容不再说明。比对方法为引脚分区级严格比对（详见完整报告 §1）。

---

## 差异 1：B12-1_HOSTIO — 3 个状态 LED 极性接反

KiCad：2 脚 → 限流电阻 → LED 网络，1 脚 → GND。
EDA：1 脚 → 限流电阻 → LED 网络，2 脚 → GND（两脚接反）。

| LED 位号 | 网络 | KiCad 接法 | EDA 接法 |
|---|---|---|---|
| D10001（pwr） | LED_PWR | 2=LED_PWR，1=GND | 1=LED_PWR，2=GND |
| D10006（image_ready） | LED_IMAGE_READY | 2=LED_IMAGE_READY，1=GND | 1=LED_IMAGE_READY，2=GND |
| D10007（model_ready） | LED_MODEL_READY | 2=LED_MODEL_READY，1=GND | 1=LED_MODEL_READY，2=GND |

## 差异 2：B12-2_HOSTIO — 4 个状态 LED 极性接反（同上方向）

| LED 位号 | 网络 |
|---|---|
| D10002（busy） | LED_BUSY |
| D10003（done） | LED_DONE |
| D10004（result_valid） | LED_RESULT_VALID |
| D10005（error） | LED_ERROR |

## 差异 3：B12-1_HOSTIO — X10001（8MHz 晶振）封装引脚编号不同

| 功能 | KiCad（ASE-4P，脚 1–4） | EDA（OSC-TH_4P，DIP 编号） |
|---|---|---|
| +5V | 脚 1、脚 4 | 脚 1、脚 8 |
| GND | 脚 2 | 脚 4 |
| OSC_OUT（时钟输出） | 脚 3 | 脚 5 |

KiCad 的 X10001-2（GND）、X10001-3（OSC_OUT）在 EDA 上无对应脚；EDA 的脚 5、脚 8 为多出。功能等价（VCC/GND/OUT 各就各位），引脚编号体系不同。

## 差异 4：KiCad 有、任何物理板上都没有的元件（11 个）

| 位号 | 说明 | KiCad 图页 | 已连接脚数 |
|---|---|---|---|
| J10001 | +5V 电源输入排针 2x02 | /B12_S10_Top_IO/ | 4 |
| J10002 | START 按键/连接器 1x02 | /B12_S10_Top_IO/ | 2 |
| J10003 | RESET 按键/连接器 1x02 | /B12_S10_Top_IO/ | 2 |
| J10004 | EXT_CLK 外部时钟输入 1x02 | /B12_S10_Top_IO/ | 2 |
| J10005 | EXPANSION 扩展排针 2x32（H_A0–H_A15 主机地址总线等） | /B12_S10_Top_IO/ | 64 |
| JP10001 | CLK_SEL 时钟选择跳线 1x03 | /B12_S10_Top_IO/ | 3 |
| J20002 | B01 第 2 个背板排针 2x20 | /B01_Conn/ | 25 |
| J20403 | B05 第 3 个背板排针 2x20 | /B05_Conn/ | 15 |
| J20603 | B07 第 3 个背板排针 2x20 | /B07_Conn/ | 15 |
| J21003 | B11 第 3 个背板排针 2x20（FC2 存储请求组） | /B11_Conn/ | 34 |
| J4001 | LOAD/PROG 下载排针 2x12 | /B03_S04_Memories/ | 21 |

另：KiCad 的 36 个测试点（TP*）物理板未放置（重建时已知排除项）。

## 差异 5：网络命名不一致（连接本身一致，仅名称不同）

| 板卡 | 网络 | KiCad 名称 | EDA 名称 |
|---|---|---|---|
| B05-1_POOL1 | 同一引脚分区 | data0 | data4 |
| B07-1_POOL2 | 同一引脚分区 | data0 | data4 |

---

## 结束语

除以上 5 项外，47 块板（B13_LUT_REF 无 KiCad 参照除外）的芯片级网络连接与 KiCad 参照**完全一致**：排除排针、LED、X10001 相关引脚后，全部板卡差异为 0（含 B12-1/B12-2 复核）。
