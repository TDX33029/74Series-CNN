# 五模型独立审查联合结论（最终汇总）

日期：2026-11-05  
主工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`  
审查对象：S00–S18 层次原理图、导出的层次网表、12 项 SPICE/逻辑仿真、ERC/BOM

> **2026-11-05 后续更新（S17/S18 集成后）**：M-09 已关闭——S09 的最后一个
> `Requant_Block` 已替换为 S17 门级核心，FC2 signed-32 四字节 LE 与 FC2 微程序
> 已实现，S18 提供 `MEM_SEL=29` 参数装载。当前 `sim/run_all.py` **12/12**，
> 顶层 ERC **0E/3434W**，审计 **2 单节点 / 0 未展开总线 / 1 DONE 驱动**，
> BOM **2845 件 / 1941 DIP / 12 个 LUT 块符号**。仍未关闭：M-08、M-10、M-11、
> M-13，以及 S09 本地 FSM 微码镜像。

## 0. 一句话结论

十一个模块级 SPICE/逻辑仿真全部通过（11/11），系统级网表最初存在真实的断链：阶段启动/完成握手、引擎到 S04 的地址与存储控制、S02 的 REQ/ACK 握手、Requant 参数总线。  
本轮已修复：Pool/Argmax 的 START（M-01）、DONE 双驱动（M-04）、Conv2 HWC→CHW 地址（M-12）、S11 总线适配层（M-02/M-03/M-06，单节点模块网 90→4）、S12 数据拼装（M-07，顶层 ERC 40E→0E）。  
S13/S14/S15/S16 已关闭 S07/S08 的 Requant（M-05 的 S07/S08 部分）；S09 FC1/FC2 仍因 FC2 signed-32 未实现而保留宏（M-09 未全关）。仍未修复：LUT lane 映射（M-08）、10–100 Hz 时序（M-10）、BOM 封装（M-11）、S02 未用译码输出（M-13）。Argmax 四字节 REQ/ACK 事务已由 S06/S04/S11/S12 闭环，因此仍不能据此认为硬件可以一次成功，但剩余项已收窄到 S09/LUT/时序。

## 1. 五个模型的实际执行情况

| 计划槽位 | 实际模型/上下文 | 状态 | 产物 |
|---|---|---|---|
| Gemini 3.8 Flash High | `5c9a4bbc.../gemini-3.8-flash-high$xhigh` | 两次失败：`empty_stream`，无报告 | `gemini-3.8-flash-high/` 为空 |
| Muse Spark 1.3 Contributor | 原 provider 多次 `invalid_request`；改用 DeepSeek 独立会话上下文 | 部分完成，报告未落盘；证据与日志完整 | `muse-slot-session-model/` |
| qwen3.8-flash | 模型未配置；仅启动了一个网表解析子任务 | 无最终报告 | `qwen-slot-netlist-review/netparse.py` |
| Beam Free | `new-provider-3/beam-free$xhigh` | 跑完全部测试/ERC/网表，最终 API `ECONNRESET`，无 REPORT.md | `beam-free/`（网表、ERC、commands.log、joint_audit.py） |
| Iceman Contributor Free | `new-provider-3/iceman-contributor-free$xhigh` | 完成 | `iceman-contributor-free/REPORT.md` + `findings.json` |
| 主进程 | 独立网表审计 + 规格对照 | 完成 | `MAIN_PROCESS_FINDINGS.md`、`main_findings.json`、`output/top.audit.json` |

说明：用户要求的“五个模型各自独立报告”没有全部拿到。Gemini 两次空流、Muse provider 拒绝、qwen 未配置、Beam 最终连接被重置。下面把**已经真实产生的证据**按“模型/上下文”归档，不把替代上下文冒充原模型；`MODEL_ASSIGNMENTS.md` 记录替换关系。

## 2. 各方结论对照

| 结论 | Iceman | Beam（部分） | Muse-slot（DeepSeek） | 主进程 | 判定 |
|---|---|---|---|---|---|
| 11/11 模块仿真通过 | 是 | 是 | 是 | 是 | 接受；后续 FC 专项后为 12/12 |
| 顶层 ERC 初始 42 个 `pin_not_driven`（现 0 个） | 是（但把 940/42/898 写反） | 是（0E/2479W） | 是 | 是（32+8 由 S12 修复） | 接受，修正 Iceman 计数表述 |
| Pool/Argmax 的 START 未接到 S01 阶段脉冲 | 是（F-006，列为 minor） | 是（joint_audit FAIL） | 是（3 个 FAIL） | 是（M-01，blocker） | **确认，已修复** |
| DONE 双驱动 | 是（F-007，列为 minor） | 是（WARN） | 是（FAIL） | 是（M-04，blocker） | **确认，已修复** |
| 引擎地址/存储控制未到 S04 | 是（F-002，medium） | 是（C1/C2/FC_ADDR FAIL） | 是（16×3 网 0 到达） | 是（M-02/M-03，blocker） | **确认，已修复（S11）** |
| S02 REQ/WE 无驱动、ACK/DONE/BUSY 无消费者 | 部分（F-001） | 是（joint_audit FAIL） | 是（FAIL） | 是（M-06，blocker） | **确认，已修复（S11）** |
| 12 个 LUT_Mult_Unit vs 4 lane/8 ROM | 是（F-003） | 未单列 | 未单列 | 是（M-08） | **确认，未修复** |
| Requant 只是宏、未展开 | 是（F-004，medium） | 未单列 | 未单列 | 是（M-05/M-09，blocker） | **已全部修复**（S13/S15/S17；FC2 signed-32） |
| 10–100 Hz 与 8 MHz/等待/超时假设冲突 | 未验证 | 未验证 | 未验证 | 是（M-10） | **确认，未修复** |
| BOM 490 片不含 18 个未展开块 | 部分（列出块） | 未单列 | 是（861 位号/490 IC） | 是（M-11） | **部分修复（现 2845 件/1941 IC/12 个 LUT 块）** |
| Pool1_OUT→Conv2 输入地址不一致 | 未发现 | 未发现 | 是（1 个 FAIL） | 复核确认 | **确认（M-12），已修复** |
| S02 读/写等待值接反 | 未发现 | 未发现 | 是（FAIL） | 复核为误报 | **否定** |
| S01 首个 START/最后一个 FINISH 检查失败 | 未发现 | 未发现 | 是（2 个 FAIL） | 复核为 harness 采样错位 | **否定** |
| S02 74HC138 五个输出无负载 | 未发现 | 未发现 | 是（FAIL） | 复核为低风险冗余 | **降级（M-13）** |

## 3. 已确认问题清单

编号沿用 `main_findings.json`，新增 M-12/M-13；M-14 已复核为误报并移除。

| ID | 严重度 | 问题 | 状态 |
|---|---|---|---|
| M-01 | blocker | `P1_START/P2_START/ARGMAX_START` 只在 S01，S05/S06 用通用 `START` | **已修复** |
| M-02 | blocker | `C1/C2/FC_ADDR`、`Cx_MEM_nCE_*` 单节点，未到 S04 | **已修复（S11）** |
| M-03 | blocker | `MEM_DATA0..7`、`MEM_ACK/DONE/BUSY` 未接 S04/引擎 | **已修复（S11）** |
| M-04 | blocker | `DONE` 由两个 74HCT541 输出同时驱动 | **已修复** |
| M-05 | blocker | Requant 参数总线（`B_DATA/M/SHIFT/ZP_*/N_MACS`）未展开 | **S07/S08/S09 已修复**（S13/S14/S15/S16/S17/S18） |
| M-06 | blocker | S02_MEM_IF 的 `REQ/WE/nCE/nOE/nWE/ACK/DONE/BUSY` 未连通 | **已修复（S11）** |
| M-07 | blocker | 顶层 42 个 `pin_not_driven` 是内部数据/控制输入，不是连接器 | **已修复（ERC 0）**：S12 接 Pool/Argmax 数据；S06/S04/S11 完成 4 字节 REQ/ACK |
| M-08 | major | 12 个 LUT 符号 vs 4 条共享 lane/8 片 27C512 | 未修复 |
| M-09 | major | Requant_Block 是架构宏，未门级实现 | **已修复**：S13/S15 + S17 门级化；FC2 signed-32 四字节 LE |
| M-10 | major | 10–100 Hz 外部时钟破坏默认等待/超时/脉冲假设 | 未修复 |
| M-11 | major | BOM 490 片不含 18 个未展开块；封装/去耦缺失 | 部分修复（现 2845 件 / 1941 IC / 12 个 LUT 块符号） |
| M-12 | blocker | Conv2 输入按 HWC 取址，Pool1 输出/规格是 CHW | **已修复** |
| M-13 | low | S02 74HC138 五个状态输出无负载，产生 ERC 孤立标签 | 未修复（不影响功能） |

### M-12 细节（已修复）

- 规格第 2 节：所有多通道特征图统一 CHW，`ADDR(c,y,x)=c*H*W+y*W+x`。
- S05 Pool1 实际写地址：`c*144 + y*12 + x`（CHW）。
- S08 Conv2 原读地址：`(oy+ky)*96 + (ox+kx)*8 + ic`（HWC）。
- 1152 个 Pool1 字节中只有 2 个能被 Conv2 按原地址读回；`sim/gen_engine_tb.py` 的 golden 与 SPICE B 源也用了 HWC，所以模块仿真“通过”并不能发现这个级间错误。
- 修复：`IN_ADDR = ic*144 + (oy+ky)*12 + (ox+kx)`；同步 golden/SPICE/图纸注记；主工程已应用并验证（11/11、layout harness PASS、0E/2479W）。
- 附带发现：旧的 `SY96 = SY*128 - SY*32` 链因二补码符号扩展不完整，实际输出 `96*SY + 481`，即旧 Conv2 输入地址还叠加了常数 481。新 `SY12 = 8*SY + 4*SY` 链同时消除了这个偏移。详见 `repair_m12/REPAIR_REPORT.md` 第 10 节。

### M-02/M-03/M-06 细节（已修复，S11）

- 新增 `S11_BusFabric`：4×74HC148（master + 3 个区域编码）、2×74HC157（区域 mux）、27C512 映射 ROM（`{FC_SEL,MASTER,REGION}` → `MEM_SEL[4:0]`）、2×74HCT541（`ADDR[23:16]` 标签、`MEM_SEL` 缓冲）、74HC32/74HC08（REQ/WE 合并）。
- S04 增加 6×74HCT541，把 `C1/C2/FC_ADDR[15:0]` 汇入共享 `ADDR[15:0]`，OE=`Cx_BUSY_N`；S10 主机缓冲与 S11 推理缓冲用 `LOAD_EN`/`NOT_LOAD_EN` 互补。
- S07/S08/S09 删除 3 个 `S02_MEM_IF` 占位块；`MEM_nCE/nOE/nWE/ACK/DONE/BUSY` 改全局；`Cx_MEM_REQ/WE` 送 S11；地址 541 OE 改为 `Cx_BUSY_N`。
- S02 删除重复的 U10（MEM_DATA 245），S04 U36 是唯一 `MEM_D<->DATA` 缓冲。
- S01 用微码 spare 位 13/14 产生 `POOL_SEL`/`FC_SEL`。
- 验证：单节点模块网 90→**4**，未展开总线 27→**21**；后续 S13/S15 集成后单节点 3、未展开 7，11/11 仿真通过，布局 harness 0 failures；S02/S04 harness 的 REQ/WE、ACK/DONE/BUSY、Cx_ADDR 全部 PASS。
- 剩余 4 个单节点：`FC_MODE_SPARE`、`POOL_BUSY`、`ARGMAX_BUSY`、`ARGMAX_RESULT_VALID`（状态回送，后续工作）。
- 详见 `repair_bus/REPAIR_REPORT.md`。

### S12 数据拼装（M-07 剩余数据输入）

- S12 U1 74HCT541：`DATA[7:0]` → `IN_DATA[7:0]`（Pool 输入缓冲）。
- S12 U2–U5 4×74HCT574：按字节锁存 score，输出组成 `SCORE_DATA[31:0]`；U6 74HC238 用 `SCORE_ADDR[1:0]`/`SCORE_RD` 译码四个锁存时钟。
- 顶层 ERC 40 errors → **0 errors / 2479 warnings**；网表审计 3 单节点/7 未展开总线/1 DONE 驱动；11/11 仿真通过；布局 harness PASS；BOM 917→953（S12）→2158（Requant 集成后）。
- 四字节事务：S06 增加 2 位字节计数器（U39）和 `{CLASS,BYTE}` 地址（U38）；S04 U50/U51 在 `ARGMAX_BUSY_N` 期间把地址零扩展到 `ADDR[15:0]`；S11 把 Argmax 作为 master 4、ROM A7=`MASTER2`，全部 region 映射到 `MEM_SEL=6`，`REQ` 合并 `SCORE_RD`；S12 改为在 `MEM_ACK` 锁存。
- Harness：`sim/harness_argmax_s12.py` 验证 40 个字节地址、S12 四 lane 拼装和 3 组 signed32 argmax；`sim/run_all.py` 11/11（含 requant）。
- 详见 `repair_s12/REPAIR_REPORT.md`、`repair_argmax4/REPAIR_REPORT.md`。

## 4. 被否定或降级的主张

### 4.1 “S02 读/写等待值接反” — 误报

Muse harness 看到 `gen_timing_tb.py` 里 `waitr=2, waitw=3`，而图纸 U2007 的 I0（读）=3、I1（写）=2，于是判定接反。  
实际 TB 的 `we` 是高=读、低=写（`Bnwe`/`Bnoe` 的极性可证），`Bwaitv = we ? waitw : waitr` 在 read 时选 3、write 时选 2，与图纸一致。只是变量命名 `waitr/waitw` 与数值语义相反，属于可读性问题，不是功能错误。建议后续把 TB 变量改名为 `wait_read/wait_write`。

### 4.2 “S01 首个 START 没有产生 G_C1_START” — harness 采样错位

S01 的阶段输出经过 74HCT574 寄存，harness 在“状态刚跳到 3”的同一拍读取的是状态 2 的输出字，所以看到 `stage=0`。状态序列本身 0→1→2→3→…→17→18→2 正确，后续每个 WAIT 的 `stage=i+1` 检查全部通过。  
“AM_WAIT done -> FINISH” 也是同类问题：harness 在进入 FINISH 后又多走了一步才检查，实际 `state=18` 且 `done=1, rv=1`，输出正确。两处均应视为测试脚本 off-by-one，不是硬件缺陷。

### 4.3 “S02 74HC138 五个输出无负载” — 低风险冗余

`CAPTURE_N/DONE_ST_N/HOLD_N/RELEASE_N/WAIT_N` 确实只挂了本地标签，没有负载。但 S02 的 `nCE/nOE/nWE/ACK/DONE` 是由 U3（74HCT574）寄存输出经 U5 缓冲产生，不依赖这五个组合译码输出；`IDLE_N` 仅用于 `MEM_BUSY`。因此不影响功能，只是增加了 ERC `isolated_pin_label` 告警。可在清理阶段删除或加测试点。

### 4.4 Iceman 的 ERC 计数表述 — 需修正

Iceman 写“940 Errors, 42 Warnings, 898”，实际报告是 **42 errors / 898 warnings / 940 messages**（修复后 42 errors / 899 warnings / 941 messages）。它的 F-001–F-007 方向正确，但 F-006/F-007 被标为 minor，主进程升级为 blocker；F-002/F-004 的 confidence 偏低，实际已由网表审计证实。

### 4.5 M-14 误报：74HC138 使能极性

主进程一度认为三个引擎的 74HC138 把低有效 `MEM_nCE` 接到了高有效 E2。复核 `decoder138` 的签名后确认：原调用是 `e0=GND, e1=MEM_nCE, e2=+5V`，而 74HC138 的 `~E1` 是低有效，所以原接法本来就是正确的。S11 补丁把 `MEM_nCE` 移到 `~E0` 只是可读性等价重构，不是功能修复。M-14 已从确认问题清单移除。

## 5. 修复与验证证据

修复内容：
- S05 Pool：删除全局 `START`/`DONE`；新增 `P1_START`/`P2_START` 全局输入；新增 U42A 74HC32 或门 `POOL_START = P1_START | P2_START`；U36/U37 启动门改用 `POOL_START`；U39 Y1 改为页内 `POOL_DONE`，P1/P2_DONE 门改用 `POOL_DONE`。
- S06 Argmax：全局 `START` 改为 `ARGMAX_START`，U36B/U37B 启动门同步。
- S00/S05/S06 图纸文字、连接矩阵、HW_MANUAL 同步。

验证：
- 网表审计（修复前 → 修复后）：单节点模块网 93 → **90**；未展开总线 27 → **27**；`DONE` 的 74HCT541 输出 2 → **1**；`P1_START/P2_START/ARGMAX_START` 均出现 2–3 个节点并到达 S05/S06。
- 9 项仿真：**11/11 PASS**（`output/sim_run_all_after_f1f5.log`）。
- 顶层 ERC：**42 errors / 899 warnings**（新增 1 条 U42 未用单元告警；无新增 error）。
- Muse S01 harness 复跑：阶段连通 7/7 PASS，DONE 单驱动 PASS；只剩上述 2 个 harness 误报。
- 补丁与前后审计：`output/model_reviews/repair_f1f5/`。

M-12 与 S11：
- Conv2 输入改为 CHW，`INA = ic*144 + (oy+ky)*12 + (ox+kx)`；golden/SPICE/注记同步，layout harness PASS，11/11 保持通过。证据 `repair_m12/`。
- S11 总线层：单节点模块网 90→4、未展开总线 27→21、顶层 ERC 0E/2479W→0E/2479W；S02/S04 harness 的 REQ/WE、ACK/DONE/BUSY、Cx_ADDR 全部 PASS，布局 harness 0 failures。证据 `repair_bus/`。

## 6. 剩余高风险与建议修复顺序

1. **M-05/M-09 Requant**：S07/S08/S09 已用 S13/S14/S15/S16/S17/S18 门级展开并验证（103 + 81 项 TB，顶层 0E）；FC2 signed-32 四字节 LE 与微程序已完成。
2. **M-08 LUT**：把 12 个逻辑 `LUT_Mult_Unit` 明确映射到 4 条物理 lane + 8 片 27C512，BOM 只计物理 ROM，逻辑符号标注“lane view”。
3. **M-10 时钟**：10–100 Hz 下等待/超时全部要重算；S11 的 MEM_SEL 路径增加约 100–150 ns，写等待建议从 2 改 3 或实测。
4. **M-11 BOM**：把 12 个 LUT 块按实际门数展开后再出 BOM；补封装、去耦、扇出缓冲。
5. **M-13 清理**：删除 S02 未用的 74HC138 输出标签或加测试点，减少 ERC 噪声。
6. **状态回送**：`POOL_BUSY`、`ARGMAX_RESULT_VALID` 仍无消费者，`FC_MODE_SPARE` 为备用；建议接 S10 状态口或 S01 监测。

## 7. 文件索引

- 主进程审计：`MAIN_PROCESS_FINDINGS.md`、`main_findings.json`、`../top.audit.json`
- 联合评审（本文件）：`FINAL_JOINT_REVIEW.md`
- 一致性矩阵：`AGREEMENT_MATRIX.md`
- 模型可用性/替代：`MODEL_ASSIGNMENTS.md`
- F1/F5 修复：`repair_f1f5/`（patch、net_changes、前后 audit、sim log）
- M-12 修复：`repair_m12/`（patch、位级穷举、layout harness）
- S11 总线修复：`repair_bus/`（patch、audit、ERC、harness、bus map）
- S12 数据拼装：`repair_s12/`（设计、网表/ERC/仿真证据）
- 设计/后续：`../docs/BUS_FABRIC_REPAIR_PLAN.md`、`../docs/REQUANT_LUT_EXPANSION_PLAN.md`
- Iceman：`iceman-contributor-free/REPORT.md`、`findings.json`
- Beam 证据：`beam-free/`（网表、ERC、commands.log、joint_audit.py）
- Muse-slot 证据：`muse-slot-session-model/`（net_audit、S01/S02/layout harness 与日志）

## 8. 审查边界

- 所有模块级 SPICE 测试都是**行为级/部件级**，不覆盖层次网表的跨模块连通性；12/12 不能作为系统可制造的证明。
- 顶层修复后为 **0 errors / 836 warnings**；`SCORE_DATA[31:0]` 和 `IN_DATA[7:0]` 已分别由 4×74HCT574 和 74HCT541 驱动。Argmax 四字节读事务已由 S06 字节计数、S04 地址缓冲、S11 master 4 和 S02 REQ/ACK 闭环，并由 harness 验证。
- 10–100 Hz 的时序、扇出、传输线、电源完整性尚未做板级验证；本报告只做逻辑/网表级结论。
