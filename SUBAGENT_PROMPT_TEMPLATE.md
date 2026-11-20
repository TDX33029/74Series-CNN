# 子代理提示词模板（74CNN-BRD 每板摆放）

> 用法：复制下面【模板正文】，替换全部 `{{占位符}}`，作为每次派发 general-purpose 子代理的 prompt。
> 每个子代理只负责一块板、且 EDA 全局串行（同一时刻仅一个代理操作）。
> 占位符说明表在文末，另附 B04-2_CONV1 的填好示例。

---

## 【模板正文】

你是 PCB 摆放执行代理，负责嘉立创EDA工程 74CNN-BRD 的 **{{BOARD_NAME}}** 板全任务摆放。工程目录：D:\Document\tempPrj\74Series-CNN。

## 必读文档（开工前先读完）
1. `D:\Document\tempPrj\74Series-CNN\CHIP_PLACEMENT_SPEC.md` —— 完整操作手册。重点：§0环境准备、§1 API坑、§3 DRC阈值、§4摆放规则、§7阻容+LED附加任务（用户硬性要求）、§6.5已完成参考（{{SIBLING_BOARDS}} 已全部验收通过，结构与几何高度相似可大量参考）。
2. 网表：`D:\Document\tempPrj\74Series-CNN\netlist_compare_v2\jlc_netlists\{{NETLIST_HINT}}`。排除 GND/VCC/+5V/+VLED 电源网络后统计芯片对连线权重，按信号流分组。

## 目标板
- 板名 {{BOARD_NAME}}，PCB 文档 uuid：**{{PCB_UUID}}**（来自 BOARD_PROCESS_ORDER.json）。
{{PHASE_SCOPE}}
- 用户已手动重画板框并放置排针。**板框和排针绝对不许动**。
- 每段 JS 开头必须校验 `eda.dmt_SelectControl.getCurrentDocumentInfo().uuid === '{{PCB_UUID}}'`，不匹配立即中止返回。
- 一切以实测为准：先读板框 polygon + 排针焊盘 + 全部器件坐标范围。姊妹板多为 y 负坐标系、排针左侧竖放（焊盘 x=45/145）、y 更负端为"下"，但必须本板实测确认。姊妹板接手时多次出现"全部器件在板框外负 x 区"的上游遗留状态——若本板也是，把全部器件搬入框内（板框/排针不动）。

## 任务A：芯片摆放{{TASK_A_HEADER}}
1. 环境准备：`curl http://localhost:49620/health` 确认 edaConnected:true。若 false，`taskkill /F /IM lceda-pro.exe` → `Start-Process 'C:\Program Files\lceda-pro\lceda-pro.exe'` 等 40 秒。打开工程 `eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297')`，openDocument('{{PCB_UUID}}')。
2. 实测板框 + 排针 + 全器件坐标范围，确定坐标系和排针方位。
3. 列出全部芯片（U 开头），逐片实测焊盘 min/max + 形状（["ELLIPSE"/"OVAL"/"RECT",w,h]），按最长边算间距。已知实测值：PDIP-28 半跨 307~312/半长 650（列距 695~710、列内 1380）；PDIP-20 纵向半长可能是 450（规格表 350 不适用）；DIP-14 焊盘可能是 OVAL 78.7×59.1。每板必须重新实测，不许套表。
4. 信号流布局：rot=90 统一竖放；列内 y 间距=上片半长+下片半长+80~85；列间 x 间距=左半跨+右半跨+80（焊盘缘隙≥6）；顶/底焊盘缘距板框≥12mil；靠排针侧起排；**最右端留 ≥360mil LED 条带**。
5. **先备份**到 `D:\Document\tempPrj\74Series-CNN\{{BOARD_NAME}}_chip_layout_backup_v2_<日期>.json`。
6. 批量 toAsync 摆放（`setState_X/Y/Rotation` 后必须 `await a.done()`），分批（≤30器件/批）。批量翻层后必须回读 layer 复核（B03-4 教训：批量脚本曾误翻全部 LED 到背面）。
7. DRC：`eda.pcb_Drc.check(true,false,true)`，**Clearance Error 必须为 0**（Connection Error 正常）。有错按 objSuffix 定位微调重验（errData.position 不可信）。

## 任务B：阻容三极管+LED（芯片 DRC 通过后做）
用户硬性要求（违反=返工）：
1. **所有 R 和 Q 放背面**（layer 2），不与正面 TH 焊盘重合（背面 SMD 与正面 TH 焊盘中心距 ≥88mil）。
2. **LED 全部正面最右侧单列**（排针在最左侧）。LED 横放 **rot=0**（短边与板框平行），**竖向节距 120~122mil**（≤150 硬限；LED-TH_L5.0-W2.0-RD 横放焊盘 x±50、y 占 120），组间 **70mil**（60 会报 DRC）。
3. **从下往上三组：电源指示 → 控制线指示 → 数据线指示**，组间 ~70mil。
4. **每个 LED（含孤立 LED）的模块 Q+R1k+R10k 放对应 LED 背面正后方，同 y 一行**（B02 教训：模块与 LED 不同 y 判违规返工）。电源灯 LEDP1 无三极管时用 RP1 放同 y 背面。
5. LED 位号=被指示网络名。分组：LEDP*=电源；CLK/RST/RESET/BUSY/DONE/READY/ERROR/CE/OE/WE/REQ/ACK/DIR/LOAD/NCS/READ/TAG/MEM_SEL 等控制类=控制组；DATA/D0~D7/CNT/MC/ADDR/MADDR 等数据类=数据组。组内按位号排序。
6. "下"= 远离排针的一端（B03 系列为 y 更负端；实测确认）。
7. **先备份** R/Q/LED 原坐标到 `D:\Document\tempPrj\74Series-CNN\{{BOARD_NAME}}_passives_backup_<日期>.json`。
8. 孤立件放背面板顶空带（惯例 y=-450），避开 LED 模块行。PCB 器件数与网表可能不符（用户预放超网表），模块匹配以**实测焊盘网络电气闭包**为准。位号可能不规律（R1~R12、Q1~Q25、QTQ5），不许用位号模式推断。
9. 背面模块行靠近芯片通孔列时注意 ≥88mil 中心距（不够就 R 竖放 rot=90 + x 微调，B03-3/4 经验）。
10. 全部完成后全板 DRC：Clearance Error 必须 0。

## 姊妹板已验收参考（几何照抄，位号按本板实际）
{{SIBLING_GEOM}}

## 汇报要求（最终回复必须包含）
1. 板框 polygon 实测 + 排针位置 + 坐标系方向结论 + 器件是否原本在板框外。
2. 芯片：总数、列数、每列清单（位号+坐标）、DRC。
3. LED：总数、三组清单（位号+y，从下往上）、LED 列 x、节距、组间距、rot。
4. Q/R：总数、层、模块对应表（每个 LED 是否有同 y Q+2R；至少 5 个示例+全部例外）。
5. 备份文件路径。
6. 异常与处理。

## 注意事项
- 单位 mil。API 走 `POST http://localhost:49620/execute`，body 用 python 写 JSON 文件 + curl --data-binary（不要内联转义）。可用 `python D:\Document\tempPrj\74Series-CNN\tools\bridge_run.py <js文件> <输出文件>`。
- 你独占 EDA。每次调用前确认 health。
- 不许动：板框、排针 J 系列、丝印。
- 若 EDA 掉线（curl 超时/other side closed）：等 30 秒重试 health；连续 3 次失败则 taskkill 重启 EDA 等 40 秒，重新 openProject+openDocument 继续。
- 完成后不管成功失败都要输出完整汇报文本作为最终回复。

---

## 占位符说明

| 占位符 | 填法 |
|---|---|
| `{{BOARD_NAME}}` | 板名，如 `B04-2_CONV1`（与工程内板名完全一致） |
| `{{PCB_UUID}}` | 该板 PCB 文档 uuid（查 `BOARD_PROCESS_ORDER.json`） |
| `{{NETLIST_HINT}}` | 网表文件名提示，如 `B04-2_CONV1__s07_conv1.net` 和 `B04-2_CONV1__b04_conn.net`（目录里 `<板名>__*.net`） |
| `{{SIBLING_BOARDS}}` | 已验收姊妹板，如 `B04-1_CONV1、B03-1~8` |
| `{{PHASE_SCOPE}}` | 全做写"本板全新未处理，任务A+B全做。"；只做阶段B写"**本板芯片已完成验收，只做任务B（阻容+LED），芯片不动（除非最右列与LED条带冲突，可整体微调列x并重跑DRC）。**"；状态存疑写"**本板可能有早前中断尝试的残留（备份文件已存在），先 dump 现状比对备份，判断已摆/未摆，再决定续做或重做。**" |
| `{{TASK_A_HEADER}}` | 全做留空；只做阶段B写"（跳过/已验收，勿动）" |
| `{{SIBLING_GEOM}}` | 姊妹板具体几何（列 x 值、LED x/节距、Q/R 列 x），从 `CHIP_PLACEMENT_SPEC.md` §6.5 抄 |

---

## 示例：B04-2_CONV1（可直接用，替换 `<日期>` 为当天）

- `{{BOARD_NAME}}` = `B04-2_CONV1`
- `{{PCB_UUID}}` = `1595c28f09776867`
- `{{NETLIST_HINT}}` = `B04-2_CONV1__s07_conv1.net` 和 `B04-2_CONV1__b04_conn.net`
- `{{SIBLING_BOARDS}}` = `B04-1_CONV1（同系列）、B03-1~8`
- `{{PHASE_SCOPE}}` = 状态存疑句（见上表），因为目录已存在 `B04-2_CONV1_chip_layout_backup_20261120.json`
  与 `B04-2_CONV1_passives_backup_20261120.json`（早前中断尝试产物）。
- `{{SIBLING_GEOM}}` =
  ```
  - B04-1（阶段A参考）：33片9列 rot=90，列 x=450/845/1220/1600/1980/2366/2765/3150/3535，列距380~395、列内780
  - B03系列（阶段B参考）：LED x=3822.5 rot=0 节距122 组间70；Q x=3565 rot90 与LED同y；R10k x=3410 / R1k x=3475 同y；LEDP1 同y RP1；孤立件背面 y=-450 空带
  ```

---

## 派发与验收流程（主代理执行）

1. 用本模板填好 → `Agent(subagent_type='general-purpose', prompt=...)`，一次只派一个。
2. 子代理返回后主代理独立验收：
   - `python tools/eda_dump_positions.py <uuid> <out.json>`
   - `python tools/verify_layout.py <out.json>`
   - `python tools/eda_drc.py <uuid>`
   - 人工核对三组清单顺序（电源→控制→数据）
3. 通过 → 把该板最终布局追加到 `CHIP_PLACEMENT_SPEC.md` §6.5 → 派下一板。
   违规 → 修复（可直接改，或 SendMessage 让同一子代理续跑）→ 复验。
