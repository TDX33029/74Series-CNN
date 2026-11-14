# LED 规模扩展完成报告（2026-11-14）

## 结果

全部 47 块生产板（A000 模板除外）LED 数量均 ≥ 20 颗：

- 原本已 ≥20 的 11 块板未动：B01(24)、B02(22)、B03-1(20)、B05-1/2(31)、
  B07-1/2(31)、B10-1/2(35)、B13(24)。
- 其余 **37 块板各补充至正好 20 颗**，全部位于**主器件页**（无连接器的那页），
  排布在该页原有内容右侧的 4 列阵列，每个模块上方有网络名文本标签。

新增模块总数：**445 个**（每个 = HLMP-S301 LED + S8050 SOT-23 + 1kΩ 0402 +
基极电阻 0402），新增器件 1780 个、导线 3115 段、文本 445 个。

## 被指示信号的选择

- 优先状态/控制类：START、DONE、BUSY、ACK、ERROR、READY、VALID、LAST、
  SAT、REQ（如 B01 的 BUSY_I/DONE_I/ERRCODE0-3、B04 的 KX/KY/OX/OY_LAST、
  B08/B09 的 PSUM/SAT 等）
- 其次使能/选通类：EN、PE、STB、LOAD、SEL、CLK、RESET、WE、OE
- 再次数据/地址/累加类：DATA、ADDR、ACC、SUM、PSUM、OUT
- 已有 LED 的网络自动跳过（创建前追踪每个现有 Q 的基极→10k→网络），
  同一网络不重复加灯
- 共享总线的基极电阻加大：3–8 板共享 → 47kΩ，>8 板（CLK/DATA 等背板总线）
  → **100kΩ**（47 板全挂也只约 2mA/线）；板内本地信号用 10kΩ

## 执行过程

1. `led_expand_prim.py --apply`：37 板批量创建；每个模块创建前在 JS 内校验
   活动文档 UUID（防另一对话切页导致错位创建），全部通过、零错页。
2. `led_repair.py`：对账修复——补齐 B04-3 缺失的 4 器件 + 7 导线、
   B12-1 缺失的 7 器件 + 14 导线、B12-3 缺失的 3 器件；全部补齐。
3. B12-3 去重：14 个重复器件、3 个重复文本删除（批量重试造成）。
4. `led_audit.py` 全量审计：37 板 **lm 标记器件数 = 4×模块数（零缺失/
   零多余/零重复 uid/零重复位号），整板 LED 数全部 = 20**。

## 位置与位号

- 每板位号在扫描所得最大值之上递增（LED/Q/R 三段独立编号）。
- 所有新器件 Unique ID 以 `lm` 开头——如需回退可按此标记一键删除
  （`led_cleanup2.py`）。

## 待办：PCB 转换（未开始）

原理图 LED 已就绪，PCB 侧尚未同步。方案：逐板
`pcb_Document.importChanges()` 生成 445×4 个封装，再脚本摆位（沿板边
两排、5mm 间距网格），核对焊盘网络。**等你确认原理图无误后再执行**；
执行期间同样要求另一对话暂停写操作。

## 工具与方法（供其他对话调用）

- 方法文档：`D:/Document/tempPrj/74Series-CNN/LED_MODULE_METHOD.md`
- 脚本：`D:/tmp/jlc_brd/led_expand_prim.py`（创建）、`led_repair.py`（对账）、
  `led_audit.py`（审计）、`led_cleanup2.py`（按 lm 标记清理）
- 过程数据：`D:/tmp/jlc_brd/state/led_expand/`（prim_report.json 含每板
  网络/位号/坐标清单）
