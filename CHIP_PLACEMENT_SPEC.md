# 74CNN-BRD 芯片摆放规范（子代理操作手册）

> 由 B04-1_CONV1 实战总结（2026-11-19）。目标：把每块板子网表中的 DIP/PDIP 芯片
> 摆到板框内靠排针一侧，方向一致（rot=90 竖放），留出远端区域给 LED/电阻/三极管（用户自己处理）。
> **执行环境**：嘉立创EDA Pro + easyeda-api 桥接（端口 49620），通过
> `POST http://localhost:49620/execute`（body: `{"code": "..."}`）执行 JS。

---

## 0. 环境准备（每次会话开始）

1. 健康检查：`curl http://localhost:49620/health`。
   - 若 `edaConnected: false`：**重启嘉立创EDA**（`taskkill /F /IM lceda-pro.exe` 后
     `Start-Process 'C:\Program Files\lceda-pro\lceda-pro.exe'`），等 40 秒。
     扩展在 EDA 启动时才会连桥接，EDA 开着但桥接后启动时不会自动重连！
2. 打开工程：`eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297')`（74CNN-BRD 固定 uuid）。
3. 查板子：`eda.dmt_Board.getAllBoardsInfo()` → 找目标板名 → 用 `getBoardInfo(板名)` 取其
   `pcb.uuid`（**板子 uuid ≠ PCB 文档 uuid**）。
4. 打开 PCB：`eda.dmt_EditorControl.openDocument(pcbUuid)`，然后确认
   `eda.dmt_SelectControl.getCurrentDocumentInfo().documentType === 3`（PCB）。
5. **每段 JS 开头必须校验当前文档 uuid === 目标 pcbUuid**，不匹配立即 return（防错板）。

## 1. 关键 API 与坑

| 用途 | API | 坑 |
|---|---|---|
| 列器件 | `eda.pcb_PrimitiveComponent.getAll()` | 位号用 `getState_Designator()`，`getState_Name()` 返回的是属性模板不是位号 |
| 器件包围盒 | `eda.pcb_Primitive.getPrimitivesBBox([id])` | 返回单个对象（非数组），含丝印；**部分板必须传组件对象而非 id 数组**（B03-1 实测传 id 会崩），稳妥写法：`getPrimitivesBBox([组件对象])` |
| 焊盘列表 | `eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(id)` | 用 `p.padNumber/p.x/p.y/p.net` 直接属性；**部分板全量返回 null（B03-1/B03-4 实测）**，回退方案：`c.toAsync().getAllPins()`（async 方法可靠，返回含 pad/net/x/y 全量数据）；或 `eda.pcb_PrimitivePad.getAll()` + bbox 归属过滤 |
| 移动/旋转 | `c.toAsync(); a.setState_X/Y/Rotation(v); await a.done()` | 必须走 async 模式；**setState 后不 done 等于没改** |
| 板框 | `eda.pcb_PrimitivePolyline.getAll()[0].polygon` | 形如 `["R",0,0,3937.0079,3228.3465,0,0]`；B 系列板框 100×82mm，y 向下为负 |
| DRC | `eda.pcb_Drc.check(true, false, true)` | 第三参 true 返回错误数组；`check()` 返回值 `false` 不代表有错——**以返回数组为准** |
| 截图 | EDA 无 API。用 PowerShell 截窗口（见附录 C） | Read 工具查看 |

**单位一律 mil**（1mm=39.37mil）。坐标 y 向下为负，板框 y ∈ [-3228, 0]。

## 2. 器件分类与实测参数（焊盘，竖放 rot=90 后）

| 类型 | 器件 | 焊盘半跨 x± | 焊盘半长 y± | 焊盘直径 | 丝印(竖放宽×高) |
|---|---|---|---|---|---|
| DIP-16 HC157 | U7050,7100,7101,7102,14007,14008,14009,14010 | 145 | 350 | **63** | 356×817 |
| DIP-16 HC283 | U7091,7092,7095,7096,7097,7105,7106,7107,7108,7109,7110 | 150 | 350 | **63** | 378×798 |
| PDIP-20 273 | U7113,7114,7115 | 150 | 450 | **70.9** | 405×1007 |
| PDIP-20 574b | U7122,7123,14011 | 156 | 450 | **70.9** | 384×1032 |
| PDIP-20 574a | U7120,7121 | 145 | 350 | **63** | 356×817 |
| PDIP-14 32 | U14001,14002,14003,14004 | 150 | 300 | 63 | 414×763 |
| DIP-14 08 | U14006 | 165 | 300 | 63 | 396×768 |
| DIP-14 86 | U7187 | 150 | 300 | 63 | 366×798 |

⚠️ 其他板可能混入同系列不同封装：**每板必须先实测**（getAllPinsByPrimitiveId 取
min/max），不许直接套本表。板框尺寸也可能不同（先读 polygon）。

## 3. DRC 间距规则（实测出的硬阈值）

- TH Pad to TH Pad：焊盘**边缘间隙 ≥ 6mil**（同列同 x 相邻焊盘：中心距 ≥ 焊盘直径+6）。
  - PDIP-20（70.9 直径）与 PDIP-20 相邻列：中心距 ≥ 76.9，**取 ≥ 80mil**。
  - 普通组合（63 直径）：中心距 ≥ 69，**取 ≥ 80mil**（留余量防浮点）。
- Board Outline to TH Pad：焊盘边缘距板框 ≥ **11.8mil** → 焊盘中心距板框 ≥ 半径+11.8
  （63 焊盘 ≥ 43.3；70.9 焊盘 ≥ 47.25）。
- 丝印超板边 **DRC 不报错**，可接受（除非用户要求）。
- Connection Error（未连线）是正常状态，不算摆放错误。

## 4. 摆放规则（按此执行）

1. **方向统一 rot=90**（竖放，芯片长边沿 y 轴）。竖放后焊盘分左右两列，列 x = 中心±半跨，行 y = 中心±半长。
2. **列结构**：从左（靠排针）到右按信号流分 9 列，每列 3-4 片同宽芯片：
   - 列内上下相邻两片的 y 间距 = 上片半长 + 下片半长 + 80（≥80mil 焊盘间隙）
   - 列间 x 间距 = 左片半跨 + 右片半跨 + 80
3. **顶部约束**：每列第一片上焊盘边缘距板顶 ≥ 12mil（PDIP-20 中心 ≤ -497 附近；63 焊盘中心 ≤ -43 附近）。
4. **底部约束**：每列最后一片下焊盘边缘距板底 ≥ 12mil。
5. **靠排针约束**：第 1 列左焊盘中心距排针右焊盘列（x≈207）中心 ≥ 80mil。
6. **信号流分组**（解析网表后按数据流向排列）：
   - IO/缓冲（DATA 直连排针）→ 最左列
   - 加法器/选通 → 中间列；累加器链相邻放置（8 根线互连的芯片必须相邻列或同列）
   - 或门/与门组 → 靠其互连对象；锁存/输出 → 允许靠右（与 IO 端的长连线不可避免时接受）
   - 强连接权重（如 8 根互连线）优先于位号顺序。
7. **LED/阻容区**：板右端留 ≥ 200mil 宽的整列空区（x 从最后一列右焊盘到板右缘），
   什么都不放，用户自己摆。
8. **不动的东西**：排针 J 系列、板框 polyline、丝印文本。LED/R/Q/RP 一律不碰。
9. 网表中出现但 PCB 未摆放的芯片（如 U7116/U7150）和 PCB 有但网表没有的芯片（如 U7187）：
   照样摆（PCB 上有的都摆），U7187 这类孤立芯片放最后空位。

## 5. 执行流程（每板）

1. 环境准备（§0）→ 2. 读板框+排针焊盘范围（确认左右边）→
3. `getAll()` 拿全部芯片位号+封装名 → 4. 每片实测焊盘 min/max（一次性批量）→
5. 解析网表（仓库 `netlist_compare_v2/jlc_netlists/` 下 `板名__*.net`，排除 GND/VCC/+5V/+VLED
   电源网络后统计芯片对连线权重）→ 6. 按第 4 节规则设计网格 →
7. **备份原始坐标**（写本地 JSON：`<板名>_chip_layout_backup_<日期>.json`）→
8. 批量 toAsync 摆放 → 9. `check(true,false,true)` 验证：**Clearance Error 必须为 0**（可剩 Connection Error）→
10. 若有错：读错误条目的 `obj1/obj2 suffix + errData.minDistance + position` 定位 → 微调 → 重验 →
11. 汇报：列数、每列芯片清单、LED 区宽度、DRC 结果。

## 6. 各板坐标系差异（重要！）

- **B04-1_CONV1**：y 向下为**负**，板框 y∈[-3228, 0]，排针在板内左侧（x≈2-207，全高）。
- **B01_SUPERVISOR / B02_TIMING**：y 向下为**正**，板框 y∈[0, 3543]（100×90mm），排针在板框**外**（y≈-506，横贯板顶）。
- 每板必须先读 polygon + 排针焊盘实测确定轴向和排针位置，不许假设。

## 6.1 焊盘形状差异（B01 实测补充）

部分 PDIP-14/DIP-14（如 U1011/12/13/15）焊盘为 **OVAL/RECT 78.7×59.1**（非圆形 63/70.9），
rot90 后纵向半跨 39.35：同列行距 80mil **不足**，需 ≥85mil；DIP-16/20 部分芯片为 66.9 方形焊盘（半跨 33.45）。
→ **实测必须包含焊盘形状字段**（`p.pad` 返回 ["ELLIPSE",63,63] / ["OVAL",...] / ["RECT",...]），
按最长边计算中心距需求，不套用 63 假设。

## 6.2 用户预放件避让（B01 经验）

板上可能有用户预放的 Q/LED 组占据某些区域（如 B01 的 x∈[1830,3010] y∈[1836,3248]）。
设计布局前先读 Q/LED/R 现有坐标，芯片网格绕开这些区域；避不开时该列减员或换位。
基线 DRC 中 Q/LED 自身的压边错误**不属于摆放范围**，不修。

## 6.4 板框-内容脱节异常（B03-1/B03-2 实测确认，待用户决策）

B03-1、B03-2 两板存在**上游既有异常**：板框 polyline 在 y 正区（x[100,3837] y[100,3443]）
且内部全空，全部元件（排针、用户 LED/Q/R 预放件、芯片）在 y 负区
（B03-1 焊盘 y[-5157,-124]、x[-927,8920]；B03-2 类似）。
- **处理原则**：不动板框（规范禁改）；芯片按**内容重力方向**摆放（与排针、预放件同区）；
- 每板开工先检查：板框 polygon vs 全部焊盘 y 范围是否同区，脱节则汇报标注；
- 影响：若直接出 Gerber，板框区是空板。需用户决定是否把板框移到内容区。

### 6.4.1 板框修正方法（B03-8 已实战验证，DRC 无新增错误）

用户已确认：脱节板框全部按 B04-1 标准修正（移到内容区包住全部元件）。步骤：

```javascript
// 1. 计算内容bbox（全部焊盘范围，p.x/p.y 是焊盘中心）
const pads = await eda.pcb_PrimitivePad.getAll();
let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
for (const p of pads) { xmin=Math.min(xmin,p.x); xmax=Math.max(xmax,p.x);
  ymin=Math.min(ymin,p.y); ymax=Math.max(ymax,p.y); }
// 2. 外扩50mil得板框矩形
const x0=xmin-50, y0=ymin-50, w=xmax-xmin+100, h=ymax-ymin+100;
// 3. 构造IPCB_Polygon对象（create不接受源数组，必须先构造！）
const polyObj = eda.pcb_MathPolygon.createPolygon(['R', x0, y0, w, h, 0, 0]);
// 4. 删除旧板框 + 创建新板框（net 传空串，layer 11=Board Outline）
await eda.pcb_PrimitivePolyline.delete([旧板框.getState_PrimitiveId()]);
const np = await eda.pcb_PrimitivePolyline.create('', 11, polyObj, 10);
```

- R 模式格式：`['R', 左x, 上y, 宽, 高, 0, 0]`（y 负区时"上"=ymin-50）。
- 验证：DRC 后 Board Outline to TH Pad 错误应为 0（内容 bbox 外扩 50 天然满足 ≥11.8）。
- B03-8 实例：内容 x[-927,6287] y[-3369,-162] → 板框 `['R',-977,-3419,7314,3307,0,0]`。

## 6.5 已完成参考（续）

### B04-1_CONV1（33 片，9 列，rot=90，y 负坐标系）

```
c1 x=450:  U7123=-493, U7050=-1373, U7091=-2153, U14006=-2884   (丝印顶/底微超板边, 电气合规)
c2 x=845:  U7092=-410, U7095=-1190, U7096=-1970, U7097=-2750
c3 x=1220: U7100=-410, U7101=-1190, U7102=-1970, U7107=-2750
c4 x=1600: U7105=-410, U7106=-1190, U7108=-1970, U7109=-2750
c5 x=1980: U7113=-499, U7114=-1503, U7110=-2383
c6 x=2366: U7115=-499, U14011=-1503, U14001=-2333
c7 x=2765: U7120=-410, U7121=-1190, U7122=-2070
c8 x=3150: U14002=-410, U14003=-1090, U14004=-1770, U7187=-2450
c9 x=3535: U14007=-410, U14008=-1190, U14009=-1970, U14010=-2750
LED区: x > 3690（约 245mil 宽）
```

### B01_SUPERVISOR（最终版，2026-11-20 用户已验收 ✅，y 负坐标系 [0,-3228]）

26 片芯片 8 列 rot=90（注意：此板 y 向下为**负**，与 B02 不同）：

```
c1 x=565:    U1001=-700.45, U1002=-2156.35 (ROM对)
c2 x=1113.4: U1003=-500.45, U1004=-1549.7, U1005=-2592.3
c3 x=1510.2: U1017=-492.55, U1008=-1533.85, U1009=-2576.35
c4 x=1907:   U1010=-493.8, U1006=-1441.05, U1007=-2291
c5 x=2304.6: U1018=-398.45, U1019=-1250.35, U1011=-2048.35, U1012=-2792.45
c6 x=2711.2: U1020=-398.45, U1021=-1250.35, U1014=-2050.3, U1016=-2798.3
c7 x=3117.8: U1022=-398.45, U1023=-1250.35, U1013=-2048.35, U1015=-2792.45
c8 x=3514.6: U1024=-492.55, U1025=-1532.65, U1026=-2572.75 (比较器列)
LED 列 x=3845.5（rot=0 横放，单列，y 从 -3141.5 到 -86.5）
Q 列 x=3515（背面 layer 2）；R 成对 x=3075/3160（背面 layer 2）
DRC: Connection Error 727（正常），Clearance Error 0
```

LED 命名规律：位号是**网络名**（LED_CLK、LED_RESET_N、LEDP1、LED_ERRCODE0…），
不是 LED101 式编号。底部=电源/控制（LEDP1 等），中部=状态/数据。按 y 从小到大即
"从下往上"。

### B02_TIMING（最终版，2026-11-20 主代理验收 ✅，y 正坐标系 [0,3228]，板 100×82mm）

排针 J20101 在板框上方负 y 区竖排（x∈[50,150]），板 y=0 边为"顶"（靠排针），y=3228 为"底"。
"从下往上" = y 从大到小。11 片芯片 5 列 rot=90：

```
c1 x=260:  U2005@500, U2009@1395.5
c2 x=960:  U2001@700 (PDIP-28)
c3 x=1670: U2002@500, U2003@1551.4, U2004@2503.3
c4 x=2320: U2006@490, U2007@1345
c5 x=2990: U2008@500, U2010@1396, U2011@2139
LED 列 x=3823（rot=0 横放，节距122，组间60）：底部 LEDP1(电源) → 控制组16颗(2982.8→1152.9) → 数据组6颗(970.9→360.8)
Q 背面 x=3522 单列 rot=90 与对应 LED 同 y；R1k x=3328 / R10k x=3246 背面成对同 y
RP1 + 孤立件放背面空行 y=1062
DRC: Connection Error 428（正常），Clearance Error 0
```

教训：LED_DONE_ST_N 的模块(Q2022/R2043/R2044)初版放到了 LEDP1 行，违反"模块在对应 LED 背面正后方"，
已修复平移到其 LED 同行。**每个 LED（含网表外孤立 LED）都必须有同 y 的背面模块行**。



### B03-1_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系 [0,-3228]，板 100×82mm）

排针 J20201 竖排板内左侧（x=45/145 两列，y[-3170,-70]）。y 更负端为"下"。
10 片芯片 5 列 rot=90（PDIP-28 SRAM 半跨 312/半长 650，列距 710、列内 1380）：

```
c1 x=540:  U4002@-700, U4001@-2530 (AS6C6264 SRAM)
c2 x=1250: U4004@-700, U4003@-2530 (SRAM)
c3 x=1960: U4006@-700, U4007@-2530 (SRAM)
c4 x=2670: U4028@-750, U4034@-1750, U4027@-2630
c5 x=3050: U4020@-800 (译码器)
LED 列 x=3822.5 rot=0 节距122 组间60（实际LED焊盘跨仅±50，直径63）：
  LEDP1(-3146) → 控制9颗(-2964~-1988) → 数据11颗(-1806~-586)
Q 背面 x=3570 rot=90 与 LED 同 y；R10k x=3300 / R1k x=3380 背面同 y
LEDP1 无三极管用 RP1 限流；MEM_SEL 上拉 R4001~4006 背面板顶空带 y=-250~-450
DRC: Connection Error 491（正常），Clearance Error 0
```

教训：规范 §2 芯片表不含 PDIP-28（半跨 312），每板必须实测；DRC errData.position
可能是过期缓存（mm 单位），定位以 objSuffix 焊盘后缀为准；setState_Layer 翻面不动 x/y。

### B03-2_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系，与 B03-1 同构）

排针 J20202 左竖（x=45/145）。9 片芯片 5 列 rot=90（PDIP-28 半跨 307，列距 695→实际 540/1235/1930/2625/3165）：

```
c1 x=540:  U4009@-700, U4010@-2080 (SRAM)
c2 x=1235: U4011@-700 (SRAM), U4014@-2080 (ROM)
c3 x=1930: U4016@-700, U4017@-2080 (ROM)
c4 x=2625: U4018@-700 (ROM), U4031@-1880 (HCT541 MADDR缓冲)
c5 x=3165: U4049@-700 (HCT541 ADDR缓冲)
LED x=3822.5 rot=0 节距122 组间182: LEDP1(-3146) → 控制12颗(-2964~-1622) → 数据8颗(-1440~-586)
Q 背面 x=3565；R10k x=3410 / R1k x=3475（距 U4049 通孔列 95mil）；LEDP1 同 y 背面 RP1
DRC: Connection Error 484（正常），Clearance Error 0
```

注意：本板网表只有 2 颗 LED，PCB 实有 21 颗（用户预放超网表）——模块匹配按实测焊盘
网络电气闭包做，不依赖网表位号。C40xx 电容网表有但 PCB 无，跳过。

### B03-3_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系，与 B03-1/2 同构）

排针 J20203 左竖。接手时全部 91 件器件在板框外负 x 区（上游遗留），已全部搬入框内。
9 片芯片 5 列 rot=90：

```
c1 x=540:  U4005@-700 (SRAM), U4008@-2080 (EE 28C256)
c2 x=1250: U4012@-700, U4013@-2080 (27C512)
c3 x=1945: U4015@-700, U4019@-2080 (27C512)
c4 x=2640: U4032@-700 (HCT541 ADDR), U4048@-1880 (HC32)
c5 x=3175: U4050@-700 (HCT541 FC2_ADDR)
LED x=3822.5 rot=0 节距122 组间70（60会报DRC）: LEDP1(-3146) → 控制12(-3076~-1734) → 数据8(-1664~-810)
Q 背面 x=3565；R10k x=3410/3420 / R1k x=3475；LEDP1 同 y RP1；20/20 模块行同 y ✓
DRC: Connection Error 460（正常），Clearance Error 0
```

教训：LED 组间距 60mil 时焊盘缘隙仅 4.9mil 会报 DRC → 组间取 70mil 更稳；
U4050 通孔列旁的模块行 R 需竖放(rot=90)+x 微调以满足 ≥88mil。

### B03-4_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系，与姊妹板同构）

排针 J20204 左竖。接手时 90 件全在板框外负 x 区，已全部搬入框内。
7 片芯片 5 列 rot=90：

```
c1 x=540:  U4024@-700 (MSEL比较器)
c2 x=1250: U4025@-700, U4026@-2100 (反相器/与门链)
c3 x=1960: U4033@-700 (MADDR缓冲)
c4 x=2625: U4036@-700, U4054@-2100 (C1_ADDR/POOL2输出缓冲)
c5 x=3175: U4040@-700 (FC1_ADDR缓冲)
LED x=3822.5 rot=0 节距122 组间70: LEDP1(-3146) → 控制17颗(-3076~-1124) → 数据3颗(-1054~-810)
Q 背面 x=3565 rot=90；R1k x=3475 / R10k x=3410（U4040 旁竖放 x=3420）；LEDP1 同 y RP1
孤立上拉 R4007 背面 (3420,-480)；20/20 模块行同 y ✓
DRC: Connection Error 375（正常），Clearance Error 0
```

教训：批量脚本 setState_Layer 曾误翻全部 LED 到背面，回读才发现——**批量翻层后必须
回读 layer 复核**；本板位号有 Q1~Q10/QTQ5/R1~R12 特殊编号，不能假设位号模式。

### B03-5_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系，与姊妹板同构）

排针 J20205 左竖。接手时 91 件全在板框外负 x 区，已全部搬入框内。
6 片芯片 5 列 rot=90（全为 PDIP-20/14，半跨 150，列距 500）：

```
c1 x=540:  U4047@-700 (POOL1输入缓冲)
c2 x=1040: U4055@-700 (POOL2输入缓冲, 与U4047八线互连)
c3 x=1540: U4021@-700, U4022@-1480 (HC138译码对)
c4 x=1920: U4023@-700 (HC138)
c5 x=2300: U4030@-700 (HC74锁存)
LED x=3822.5 rot=0 节距122 组间70(实测192?): LEDP1(-3146) → 控制18颗(-2954~-880) → 数据2颗(-688/-566)
Q 背面 x=3565 rot=90；R10k x=3410 / R1k x=3475；LEDP1 同 y RP1；孤立 R4008/R4010 背面 y=-450
20/20 模块行同 y ✓
DRC: Connection Error 340（正常），Clearance Error 0
```

### B03-6_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系，与姊妹板同构）

排针 J20206 左竖。接手时 84 件在板框外负 x 区，已全部搬入框内。
6 片芯片单行 y=-700，6 列（列距 500）：

```
c1 x=540:  U4037 (C2_ADDR0-7缓冲)
c2 x=1040: U4041 (ADDR0-7缓冲)
c3 x=1540: U4038 (C2_ADDR8-15缓冲)
c4 x=2040: U4042 (ADDR8-15缓冲)
c5 x=2540: U4044 (POOL1_IN_ADDR缓冲)
c6 x=3040: U4056 (HC32或门,孤立)
LED x=3822.5 rot=0 节距122 组间70: LEDP1(-3140) → 控制7颗(-2948~-2216) → 数据13颗(-2024~-560)
Q 背面 x=3565 rot=90；R10k x=3410 / R1k x=3475；LEDP1 同 y RP1(x=3565)；孤立 R4009 (3410,-450)
20/20 模块行同 y ✓
DRC: Connection Error 355（正常），Clearance Error 0
```

### B03-7_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系，与姊妹板同构）

排针 J20207 左竖。接手时 88 件在板框外负 x 区，已全部搬入框内。
5 片芯片（全 PDIP-20 HCT541）3 列 rot=90：

```
c1 x=540:  U4043@-700, U4051@-1680
c2 x=1040: U4045@-700, U4046@-1680
c3 x=1540: U4052@-700
LED x=3822.5 rot=0 节距122 组间70: LEDP1(-3140) → 控制4颗(-2948~-2582) → 数据16颗(-2390~-560)
Q 背面 x=3565 rot=90；R10k x=3410 / R1k x=3475（全部 rot=90）；LEDP1 同 y RP1；孤立 R4002 (3410,-450)
20/20 模块行同 y ✓
DRC: Connection Error 350（正常），Clearance Error 0
```

### B03-8_MEMORY（最终版，2026-11-20 主代理验收 ✅，y 负坐标系，与姊妹板同构）

排针 J20208 左竖（板框 y 起 -5 微差，其余同标准）。接手时 86 件在板框外负 x 区，已全部搬入。
4 片芯片单行 y=-700，4 列（列距 540）：

```
c1 x=560:  U4029 (HC245 LOAD_DATA↔MEM_D收发)
c2 x=1100: U4035 (HCT541 C1_ADDR)
c3 x=1640: U4039 (HCT541 FC1_ADDR)
c4 x=2180: U4053 (HCT541 POOL2_OUT_ADDR)
LED x=3822.5 rot=0 节距122 组间70: LEDP1(-3140) → 控制6颗(-2948~-2338) → 数据14颗(-2146~-560)
Q 背面 x=3565 rot=90；R10k x=3410 / R1k x=3475（全 rot=90）；LEDP1 同 y RP1；21/21 模块行同 y ✓
DRC: Connection Error 328（正常），Clearance Error 0
```

**B03 系列 8 块板全部完成**（B03-1~B03-8，2026-11-20）。

## 7. 附加任务：阻容三极管 + LED 摆放（B01/B02/B03-1 已验收 ✅）

芯片列摆完后，同板继续处理电阻/三极管/LED（每板都要做）。

### 7.1 用户硬性要求（原话归纳，违反=返工）

1. **所有电阻和三极管放背面**（layer 2），不得与正面芯片的通孔焊盘重合。
2. **LED 放正面**，**全部在最右侧排成一排**（排针在最左侧）——不许散放到"板卡两边"或中间。
   （次要补充：重要程度低的 LED 允许放板中，但默认全放右缘单列。）
3. **LED 短边与板框平行**（= 横放 rot=0，长轴沿 x），**一颗 LED 竖向占位 ≤150mil**。
4. **排列方向从下往上分三组：电源指示 → 控制线指示 → 数据线指示**，组间留少许距离（~60mil）。
5. **每个 LED 模块的电阻三极管放对应 LED 背面附近**，便于走线。
6. 不与正面 TH 焊盘冲突：背面 SMD 与正面通孔焊盘中心距 ≥88mil。

### 7.2 B01 实测参考几何（照抄可用）

- LED 封装 LED-TH_L5.0-W2.0-RD：**rot=0 横放**时焊盘 x 跨 290mil（两 TH 焊盘 ±145），
  y 向占 120mil（含焊盘）。竖排节距 125mil ✓（≤150）。
- 25 颗 LED 单列：x=3845.5，y 从 -3141.5 每 125mil 一颗到 -86.5。
- 24 只三极管 S8050（SOT-23）：背面 x=3515 单列，rot=90，与 LED 同 y。
- 48 颗电阻 0402 背面成对：每模块 R(1k)x=3160 + R(10k)x=3075，与 LED/Q 同 y。
- 芯片 c8 列需左移压缩，给 LED 条带腾出 ≥360mil（LED 焊盘左缘 ≈ 3700，
  距 c8 焊盘右缘 ≥80）。
- LED 组内可用 125mil 节距；**若 25 颗放不下（板高不足），节距可压到 120mil**。

### 7.3 分组方法

1. LED 位号 = 被指示网络名（LED_CLK、LEDP1、LED_ERRCODE0…）。
2. 电源组：LEDP*（电源指示灯）。
3. 控制组：CLK/RST/RESET/START/BUSY/DONE/READY/ERROR 等控制类信号。
4. 数据组：DATA/ERRCODE/RESULT/IMG/MDL 等数据类信号。
5. 从下往上（y 递减方向注意坐标系：B01 是 y 负区，"下"=y 更负端）依次放
   电源→控制→数据；每组内按位号排序。

### 7.4 执行顺序（每板）

1. 备份当前 R/Q/LED 坐标（`<板名>_passives_backup_<日期>.json`）。
2. 若最右列芯片距板右缘 < 360mil：先微调芯片列 x（等距压缩列距），重跑 DRC。
3. 摆 LED（正面 rot=0 单列，三组顺序）→ 摆 Q/R（背面，对应 LED 正后方，
   Q 与 LED 同 y；R1k 在 Q 右侧、R10k 再右）。
4. 全板 DRC：Clearance Error 必须 0。
5. 汇报：LED 总数、三组清单（位号+坐标）、每模块 Q/R 坐标、DRC 结果。
6. **每个 LED（含网表外孤立 LED）必须有同 y 的背面 Q/R 模块行**——B02 初版曾把
   LED_DONE_ST_N 的模块放到电源 LEDP1 行（不同 y），被判验收违规返工。

## 附录 A：批量摆放 JS 模板

```javascript
const TARGET = '<pcbUuid>';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const plan = [['U7101', x, y], ...]; // [位号, x, y]，rot 统一 90
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) continue;
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
}
return 'placed ' + plan.length;
```

## 附录 B：DRC 结果解析 JS

```javascript
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
return arr.map(c => ({name: c.name, n: (c.list||[]).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)}));
// 期望输出: [{"name":"Connection Error","n":<若干>}] —— Clearance Error 必须不存在或为 0
```

## 附录 C：EDA 截图（PowerShell）

```powershell
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
$p = Get-Process lceda-pro | Where-Object { $_.MainWindowTitle -ne '' } | Select-Object -First 1
# (SetForegroundWindow + GetWindowRect + CopyFromScreen → 存 png)
```
截图用于人眼复核，非必需步骤。
