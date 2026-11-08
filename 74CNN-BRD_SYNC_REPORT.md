# 74CNN-BRD 嘉立创 EDA 重绘与网表校验报告

生成日期：2026-11-08  
工程：`TDX33029/74CNN-BRD`  
工程 UUID：`86c1d8c59be2462ebb49fab075a5c297`  
EDA 版本：嘉立创 EDA 专业版 V3.2.149.88089769

## 1. 结论

| 项目 | 结果 |
|---|---|
| 板卡数量 | 13（B01–B12 + B13_LUT_REF） |
| 图页数量 | 33（20 功能页 + 12 连接器页 + 1 参考页） |
| 器件总数 | 1078（不含电容） |
| 逐板网表比对 | 12 块正式板 + B13 全部 0 mismatch / 0 only_kicad / 0 only_eda |
| 器件来源 | 嘉立创商城器件库，全部 DIP / 直插 |
| KiCad 数据导入 | 无；全部为原生放置 + 连线 + 网络标签 |

## 2. 约束落实情况

- **未导入任何 KiCad 数据**：所有器件均通过 `lib_Device` 从嘉立创库原生放置，导线与网络标签由 API 逐引脚创建。
- **封装**：逻辑 IC 全部 PDIP/DIP；电阻为轴向金属膜直插；排针 2.54mm 直插；LED、测试点、轻触开关、晶振均为直插。
- **电容全部移除**：KiCad 中的 274 个 `Device:C`（100n/100nF/1u/10u）未放置，其引脚已从比对基线中剔除，供后续手工补加。
- **连接方式**：每个引脚引出一段 30 单位短线，并在导线上写入与 KiCad 完全一致的网络名，实现“引脚网络标签”。同名网络在同一块板内跨页自动合并。
- **旧工程 74CNN 未改动**；KiCad 源文件只读。

## 3. 板卡与图页

| 板名 | 图页 | 器件数 | 引脚/导线数 |
|---|---|---|---|
| B01_SUPERVISOR | S01_Supervisor, B01_Conn | 35 | 555 |
| B02_TIMING | S02_Timing, B02_Conn | 21 | 230 |
| B03_MEMORY | S04_Memories, B03_Conn | 83 | 1792 |
| B04_CONV1 | S07_Conv1, S13_Requant_C1, B04_Conn | 169 | 2754 |
| B05_POOL1 | S05_Pool1, S12A_PoolLatch1, B05_Conn | 50 | 863 |
| B06_CONV2 | S08_Conv2, S15_Requant_C2, B06_Conn | 169 | 2763 |
| B07_POOL2 | S05_Pool2, S12A_PoolLatch2, B07_Conn | 50 | 863 |
| B08_FC1 | S09_FC1, S17_FC1, B08_Conn | 168 | 2742 |
| B09_FC2 | S09_FC2, S17_FC2, B09_Conn | 168 | 2742 |
| B10_ARGMAX | S06_Argmax, S12B_ScoreLatch, B10_Conn | 56 | 887 |
| B11_BUSFAB | S11_BusFabric, S11A_EngineMerge, B11_Conn | 25 | 430 |
| B12_HOSTIO | S10_Top_IO, B12_Conn | 64 | 494 |
| B13_LUT_REF | S_LUT_Mult_1 | 10 | 140 |

## 4. 逐板网表比对

比对方法：以 KiCad 整设计 XML 网表按板卡位号集合过滤得到基线；嘉立创导出 Protel2 网表；剔除电容引脚后按“引脚连通分区”比较，不比较网络名。`unconnected` 为嘉立创对未接引脚的自动命名，不计入差异。

| 板卡 | KiCad 网络 | EDA 网络 | KiCad 引脚 | EDA 引脚 | mismatch | only_kicad | only_eda | unconnected |
|---|---|---|---|---|---|---|---|---|
| B01_SUPERVISOR | 136 | 170 | 521 | 555 | 0 | 0 | 0 | 34 |
| B02_TIMING | 53 | 80 | 203 | 230 | 0 | 0 | 0 | 27 |
| B03_MEMORY | 288 | 312 | 1768 | 1792 | 0 | 0 | 0 | 24 |
| B04_CONV1 | 724 | 823 | 2655 | 2754 | 0 | 0 | 0 | 99 |
| B05_POOL1 | 209 | 263 | 809 | 863 | 0 | 0 | 0 | 54 |
| B06_CONV2 | 733 | 821 | 2675 | 2763 | 0 | 0 | 0 | 88 |
| B07_POOL2 | 209 | 263 | 809 | 863 | 0 | 0 | 0 | 54 |
| B08_FC1 | 725 | 810 | 2657 | 2742 | 0 | 0 | 0 | 85 |
| B09_FC2 | 725 | 809 | 2658 | 2742 | 0 | 0 | 0 | 84 |
| B10_ARGMAX | 248 | 281 | 854 | 887 | 0 | 0 | 0 | 33 |
| B11_BUSFAB | 126 | 159 | 397 | 430 | 0 | 0 | 0 | 33 |
| B12_HOSTIO | 131 | 157 | 468 | 494 | 0 | 0 | 0 | 26 |
| B13_LUT_REF | 70 | 70 | 140 | 140 | 0 | 0 | 0 | 0 |

全部板卡均为 **0 mismatch / 0 only_kicad / 0 only_eda**。

## 5. 器件映射

| KiCad lib_id | 嘉立创器件 | 封装 | 商品编号 |
|---|---|---|---|
| 74xx:74HC00 | SN74HC00N | DIP-14_L20.0-W7.6-P2.54-LS7.6-BL | C2902 |
| 74xx:74HC02 | SN74HC02N | DIP-14_L19.2-W6.6-P2.54-LS10.9-BL | C2897 |
| 74xx:74HC04 | SN74HC04N | DIP-14_L19.2-W6.6-P2.54-LS10.9-BL | C2886 |
| 74xx:74HC08 | SN74HC08N | DIP-14_L19.2-W6.6-P2.54-LS10.9-BL | C2887 |
| 74xx:74HC138 | 74HC138N | DIP-16_L19.2-W6.6-P2.54-LS7.6-BL | C507188 |
| 74xx:74HC157 | SN74HC157N | DIP-16_L20.4-W5.8-P2.54-LS7.6-BL | C5218 |
| 74xx:74HC161 | SN74HC161N | PDIP-16_L19.3-W6.4-P2.54-LS7.9-BL | C273647 |
| 74xx:74HC238 | CD74HC238E | PDIP-16_L19.3-W6.4-P2.54-LS7.9-BL | C1547095 |
| 74xx:74HC245 | CD74HC245E | PDIP-20_L25.9-W6.6-P2.54-LS7.9-BL | C1548569 |
| 74xx:74HC283 | CD74HC283E | DIP-16_L19.8-W6.5-P2.54-LS7.6-BL | C139343 |
| 74xx:74HC32 | SN74HC32AN | PDIP-14_L19.3-W6.4-P2.54-LS7.6-BL | C2870258 |
| 74xx:74HC688 | SN74HC688N | PDIP-20_L24.5-W6.4-P2.54-LS7.9-BL | C354413 |
| 74xx:74HC74 | CD74HC74E | PDIP-14_L19.3-W6.4-P2.54-LS7.9-BL-1 | C354059 |
| 74xx:74HC85 | CD74HC85E | DIP-16_L20.0-W6.4-P2.54-LS7.6-BL | C134106 |
| 74xx:74HCT245 | SN74HCT245N3 | PDIP-20_L25.9-W6.6-P2.54-LS7.9-BL | C3587547 |
| 74xx:74HCT273 | SN74HCT273N | PDIP-20_L25.4-W6.4-P2.54-LS7.6-BL | C1523188 |
| 74xx:74HCT541 | SN74HCT541N | PDIP-20_L26.2-W7.6-P2.54-LS7.9-BL | C354420 |
| 74xx:74HCT574 | CD74HCT574EE4 | PDIP-20_L25.9-W6.6-P2.54-LS7.9-BL | C17362624 |
| 74xx:74LS148 | SN74HC148N | DIP-16_L19.8-W6.5-P2.54-LS7.6-BL | C5233 |
| Connector:TestPoint | TP-黄色测试点 | TESTPOINT-TH_BD3.2 | C9900007422 |
| Connector_Generic:Conn_01x02 | PZ254V-11-02P | HDR-TH_2P-P2.54-V-M | C492401 |
| Connector_Generic:Conn_01x03 | PZ254V-11-03P | HDR-TH_3P-P2.54-V-M_PZ254V-11-03P | C2937625 |
| Connector_Generic:Conn_02x02_Odd_Even | PZ254V-12-04P-A40 | HDR-TH_4P-P2.54-V-M-R2-C2-S2.54-1 | C45384660 |
| Connector_Generic:Conn_02x10_Odd_Even | PZ254V-12-20P | HDR-TH_20P-P2.54-V-M-R2-C10-S2.54 | C492427 |
| Connector_Generic:Conn_02x12_Odd_Even | PZ254V-12-24P | HDR-TH_24P-P2.54-V-M-R2-C12-S2.54 | C492429 |
| Connector_Generic:Conn_02x16_Odd_Even | PZ254V-12-32P | HDR-TH_32P-P2.54-V-M-R2-C16-S2.54 | C22465940 |
| Connector_Generic:Conn_02x20_Odd_Even | PZ254V-12-40P | HDR-TH_40P-P2.54-V-M-R2-C20-S2.54_2-146257-0 | C22465944 |
| Device:LED | 5mm LED 雾发红 | LED-TH_BD5.0-P2.54-FD | C9900034380 |
| Device:R_Network08 | A09-103JP | RES-ARRAY-TH_9P-P2.54-D1.0 | C8692 |
| Device:R (100k) | MFR-25FBF52-100K | RES-TH_BD2.4-L6.3-P10.30-D0.6 | C1364475 |
| Device:R (10k) | MFR-25FBF52-10K | RES-TH_BD2.4-L6.3-P10.30-D0.6 | C1519255 |
| Device:R (33) | MFR-25FBF52-33R2 | RES-TH_BD2.4-L6.3-P10.30-D0.6 | C1372428 |
| Device:R (470) | MFR-25FBF52-470R | RES-TH_BD2.4-L6.3-P10.30-D0.6 | C1369905 |
| Memory_EEPROM:28C256 | AT28C256-15PU | PDIP-28_L37.0-W13.5-P2.54-LS15.6-BL | C1348752 |
| Memory_EPROM:27C512 | AT27C512R-70PU | PDIP-28_L37.0-W13.5-P2.54-LS15.6-BL | C1523866 |
| Memory_RAM:HY6264AxP | AS6C6264-55PCN | PDIP-28_L38.1-W12.7-P2.54-LS15.3-BL | C1523874 |
| Oscillator:ASE-xxxMHz | ACH-8.000MHZ-EK | OSC-TH_4P-L12.7-W12.7-P7.62-BL-1 | C1670586 |
| Switch:SW_Push | YTS1S0161BBT00 | KEY-TH_2P-L6.0-W6.0-P5.00 | C22368614 |

特殊引脚映射（因嘉立创符号引脚编号与 KiCad 不同）：

- LED：KiCad 1=K/2=A ↔ 嘉立创 1=+/2=-，映射 1→2、2→1。
- 8MHz 有源晶振：KiCad 1=EN/2=GND/3=OUT/4=VDD → 嘉立创 1=Tri-State、4=Case GND、5=Output、8=Vdd，映射 1→1、2→4、3→5、4→8。

## 6. 校验与偏差说明

- 逻辑 IC 的未使用门/未接引脚在嘉立创网表中表现为 `UNCONNECTED-(...)` 单引脚网络，属正常现象，已单独计数。
- 布局为按位号排序的网格布局，不追求与 KiCad 图面几何一致；网络连通性与位号、器件型号、封装保持一致。
- 图页名称由嘉立创自动转为小写（如 `s01_supervisor`），板名保持大写。
- 电容位号已从两套网表中同时剔除；补加电容后需重新导出网表复核。

## 7. 视觉检查

- 每页图幅字段设为 A0（画布 4676×3304），器件按 10 列网格排列，列距 420、行距 200，引脚网络标签位于引脚外侧。
- 已抽查 S01、B01_Conn 等页面：器件与网络标签均在 A0 画布内，无重叠短路。
- 工程内图框为嘉立创默认绘图符号（A4 装饰框），与 A0 画布尺寸不一致，仅影响图框观感，不影响图页内容、网表与后续 PCB 导入。

