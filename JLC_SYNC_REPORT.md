# 74CNN 嘉立创 EDA 重绘与同步报告

日期：2026-11-07
工程：`74CNN`（`6b7464fb399341afac3f4452db9da3df`）
源工程：`Cache/CNN_74xx_System/*.kicad_sch`（未被修改）

## 1. 范围

S01–S17 中实际存在的 14 张图页：

- 已绘制：S01、S02、S04、S05、S06、S07、S08、S09、S10、S11、S12、S13、S15、S17
- 未绘制：S03、S14、S16（S03 源目录不存在；S14/S16 只在 `Cache/_archive_requant_full/sheets`，不在本轮范围）
- 未绘制任何 PCB（按要求只画原理图）

## 2. 板子与图页

| 图页 | 板子名 | 板子 UUID | 图页 UUID | part | netport | netflag |
|---|---|---|---:|---:|---:|---:|
| S01_Supervisor | `Board1` | `f6e1d58ba3e70be1` | `547b02c6c6c922f8` | 82 | 142 | 214 |
| S02_Timing | `S02_Timing_1` | `665fe4d752f6dd8b` | `974468c12991a54e` | 37 | 50 | 98 |
| S04_Memories | `S04_Memories_1` | `46743cc936140e9b` | `757acc94a6335078` | 142 | 537 | 286 |
| S05_Pool | `S05_Pool_1` | `c6d1d9bcb3c57a9d` | `a57a4c19d44c66b7` | 166 | 188 | 303 |
| S06_Argmax | `S06_Argmax_global` | `24869f1b8108c2c1` | `8cc388e8aea09808` | 149 | 632 | 258 |
| S07_Conv1 | `S07_Conv1_global` | `21dcf2509dc906a7` | `d13a2a40be8055c9` | 197 | 2560 | 0 |
| S08_Conv2 | `S08_Conv2_global` | `51d36f134ab41500` | `89ce4c14faf644fd` | 193 | 2583 | 0 |
| S09_FC | `S09_FC_global` | `e32b0802e6a01f02` | `1717e48e2c1cc77d` | 179 | 2375 | 0 |
| S10_Top_IO | `S10_Top_IO` | `1ea3b4aa13c97477` | `958657b114d1be68` | 85 | 182 | 111 |
| S11_BusFabric | `S11_BusFabric` | `5edb529dff17e2fc` | `1eec14a9e1ffa167` | 47 | 162 | 96 |
| S12_DataAssembly | `S12_DataAssembly` | `668c6a8ea5e06dc7` | `59dc483730406f42` | 18 | 162 | 33 |
| S13_Requant_C1 | `S13_Requant_C1` | `f71ec959be9fe9c7` | `98bc80eb6642ed01` | 37 | 117 | 49 |
| S15_Requant_C2 | `S15_Requant_C2` | `68f3270929f356ce` | `2bdccc4358295850` | 36 | 115 | 49 |
| S17_Requant_FC | `S17_Requant_FC` | `e9325ff08299414d` | `64adbd3dae4fdb2f` | 61 | 161 | 87 |
| **合计** | | | | **1429** | **9966** | **1584** |

> 图页名在 EDA 中为小写（如 `s01_supervisor_1`）；表中使用源图页名便于对照。板名 `_1` / `_global` 为导入时自动生成。

## 3. 处理流程

1. **导入**：通过 Bridge 调 `sys_FileManager.importProjectByProjectFile(file,"KiCad",{importOption:"ImportDocument"},{operation:"Existing Project",existingProjectUuid})`，每张图生成一个独立板子。
2. **封装**：按器件类型映射 DIP/直插封装，`otherProperty.Footprint` 传工程封装实例 UUID 字符串（不是对象）；每 40 个一批，直到 `remaining=0`。
3. **标签与网络**：
   - 普通图页：netport 由导入器保留；本地 label 补成 TEXT（仅显示，不参与电气）。
   - S06/S07/S08/S09：用“局部标签转全局标签”的临时副本导入，netport 直接承载原局部标签的网络名，保证单页内连通性与 KiCad 一致。
4. **排除非器件**：所有非 `part` 对象（netport、netflag、TEXT、sheet 等）批量写 `Add into BOM = no`、`Convert to PCB = no`。
5. **电源命名归一**：把 `#PWR*` 电源符号的 `Name` 去掉 `power_` 前缀，使 netflag 与 netport 同名合并。
6. **网表修复**：S04 拆分重叠导线；S06 重画两条标签桩线绕开电源引脚。
7. **保存与复核**：每页 `sch_Document.save()`；重新打开页面统计对象数、封装缺失、BOM/PCB 标记；导出 Protel2 网表与 KiCad 网表逐引脚对比。

## 4. 质量检查

| 检查项 | 结果 |
|---|---|
| 图页数 | 14/14 已绘制并保存 |
| 实体单元 | 1429 |
| 封装覆盖率 | 100%（`noFp = 0`） |
| 非器件 BOM/PCB 标记 | 0（`badNon = 0`） |
| 网表对比 | 14/14 通过，0 分区差异（见 `NETLIST_COMPARE_REPORT.md`） |
| 图页可视化 | 巨型电源标签 0、页外/浮空标签 0（已清理 985 个冗余电源 `ATTR` + 1 个 `_NETLABEL_`） |
| PCB | 未绘制（仅 Board1 保留一个空 PCB） |
| 源 `.kicad_sch` | 未修改 |

## 5. 主要修复记录

1. **电源网络分裂**：`power_+5V` / `power_GND` 与 `+5V` / `GND` 在 EDA 中被当成不同网络，背板排针电源脚悬空。通过重命名电源符号 `Name` 合并，S01 的 `+5V` 从 87 脚恢复到 95 脚、`GND` 从 125 脚恢复到 137 脚。
2. **S04 电源短路**：U4043/C4042 附近两条重叠导线被导入器合并，`+5V` 与 `GND` 短接（344 脚并成一个网络）。拆成两条独立导线并给 +5V 加小绕行后通过。
3. **S06 标签误并电源**：`/BYTE3`、`/FIRST` 的标签桩线跨过 U6032 的 +5V/GND 引脚。用全局标签副本重导入并重画桩线后通过；旧板 `S06_Argmax` 已删除。
4. **电源桩线巨型冗余标签（可视化）**：8 张图页的每条电源桩线上多出一个字号 196.85 的 `NET` 标签，值为 `power_+5V` / `power_GND`，渲染成覆盖整页的大字。确认导线端点有同名 netflag/netport 后从文档源删除 985 个冗余 `ATTR`，并删除 S15 的 1 个根级 `_NETLABEL_` 浮空标签；另把 `bulktext*` 文本的源坐标 `y` 取反、导入 netflag 替换为原生电源符号。逐页重导出网表复核，连接性 0 变化。

## 6. 可复现工具

- `Cache/CNN_74xx_System/tools/jlc/netlist_compare.py`：KiCad/Protel2 网表引脚分区对比。
- `tools/jlc/jlc_batch.py`：封装批次、标签批次、排除批次。
- `Cache/CNN_74xx_System/tools/jlc/process_page.py`：已导入页面的封装/标签/标记处理。
- `Cache/CNN_74xx_System/tools/jlc/sync_new_sheet.py`：新图页导入→封装→标签→标记→验证。
- 本轮临时脚本与中间数据：`D:/tmp/jlc_netlist/`、`D:/tmp/jlc_sync/`（不属于工程源码）。

## 7. 收尾

- `Signal.txt` 已清空为 0 字节（下次定时触发读到非 1 会立即退出）。
- `.jlc_sync.lock` 已删除。
- 说明：本会话没有 `CronPauseSelf` 工具，`CronList` 也为空（该定时任务未注册在当前工作区），因此无法在会话内直接暂停 `automation-e01fb416-8edb-46e7-84d6-b77550b18559`。Signal 已清零，后续触发不会执行任何操作；如需彻底停用，请在宿主的自动化页面手动暂停该任务。
