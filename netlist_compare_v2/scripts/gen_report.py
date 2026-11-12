#!/usr/bin/env python3
"""Generate the Markdown difference report from results/compare_raw.json."""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'results', 'compare_raw.json')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    BASE, '..', '74CNN-BRD_NETLIST_DIFF_REPORT_2026-11-12.md')

d = json.load(open(RAW, encoding='utf-8'))
by = {e['board']: e for e in d['boards']}
order = json.load(open(os.path.join(BASE, 'boards_pages.json'), encoding='utf-8'))['result']
order = [b['board'] for b in order]

kicad_only_meta = {
    'J10001': ('+5V 电源输入排针 2x02', '/B12_S10_Top_IO/', 4),
    'J10002': ('START 按键/连接器 1x02', '/B12_S10_Top_IO/', 2),
    'J10003': ('RESET 按键/连接器 1x02', '/B12_S10_Top_IO/', 2),
    'J10004': ('EXT_CLK 外部时钟输入 1x02', '/B12_S10_Top_IO/', 2),
    'J10005': ('EXPANSION 扩展排针 2x32（H_A0–H_A15 主机地址总线等，64 脚全连接）', '/B12_S10_Top_IO/', 64),
    'JP10001': ('CLK_SEL 时钟选择跳线 1x03', '/B12_S10_Top_IO/', 3),
    'J20002': ('B01 背板排针 2x20（第 2 个，25 脚连接）', '/B01_Conn/', 25),
    'J20403': ('B05 第三块背板排针 2x20（15 脚连接）', '/B05_Conn/', 15),
    'J20603': ('B07 第三块背板排针 2x20（15 脚连接）', '/B07_Conn/', 15),
    'J21003': ('B11 第三块背板排针 2x20（34 脚连接，FC2 存储请求组信号）', '/B11_Conn/', 34),
    'J4001': ('LOAD/PROG 下载排针 2x12（IMAGE/LOAD 数据组，21 脚连接）', '/B03_S04_Memories/', 21),
}

L = []
w = L.append

w('# 74CNN-BRD（嘉立创EDA）↔ CNN_74xx_System（KiCad）网表连接性严格对比报告')
w('')
w('- 日期：2026-11-12')
w('- 被检工程：嘉立创EDA Pro `74CNN-BRD`（47 块板：B01、B02、B03-1…B12-3、B13_LUT_REF）')
w('- 参照工程：`D:\\Document\\tempPrj\\74Series-CNN\\Cache\\CNN_74xx_System`（KiCad 10.0，kicad-cli 导出，1315 元件 / 3859 网络）')
w('- EDA 侧数据：逐板导出原理图网表（Protel2 格式，93 个图页全部导出成功，见 `netlist_compare_v2/jlc_netlists/`）')
w('- 逐板原始数据：`netlist_compare_v2/results/compare_raw.json`')
w('')
w('## 1. 对比方法')
w('')
w('1. 在嘉立创 EDA 中逐板打开原理图图页，用 `sch_ManufactureData.getNetlistFile(..., "Protel2")` 导出整板网表（EDA 网表导出为板级：同板两页导出结果一致）。')
w('2. 用 `kicad-cli sch export netlist --format kicadsexpr` 导出 KiCad 系统总网表作为参照。')
w('3. **引脚分区严格比对**：把每个 `元件.引脚` 映射到它所在网络的引脚集合，逐引脚比较 KiCad 与 EDA 的集合（限制在本板器件范围内）是否完全一致。忽略网络名（KiCad 带层次前缀、大小写不同）、忽略 KiCad 的 `unconnected-*` 与 EDA 的 `UNCONNECTED-*` 伪网络。')
w('4. 按用户要求**忽略 EDA 后加元素**：电容（C*）、LED 模块（LED*/Q*/R* 驱动）、测试点（TP*，KiCad 有 36 个 TP、EDA 物理板未放置）在两侧均不参与比对，但全部列明。')
w('5. 差异分类：`SIGNAL` = 芯片与芯片之间连线不同（真实逻辑接线差异）；`CONN_TAP` = 芯片网络对背板排针的分接点不同；`CONN_PIN` = 排针引脚本身的网络分配不同。')
w('')
w('## 2. 总体结论')
w('')
w('| 结论项 | 结果 |')
w('|---|---|')
w('| 芯片间逻辑连线（芯片引脚 ↔ 芯片引脚） | **47 板全部一致**（B13 无参照除外） |')
w('| 芯片级真实差异 | 仅 B12 组：**7 个状态 LED 极性接反** + **X10001 晶振封装引脚编号不同**（B12-1） |')
w('| 排针（背板连接器） | **系统性差异**：KiCad 每板 2×20/40P 且电源脚在 1–4；EDA 全部改为 2×32/64P（1–4 GND、5–8 +5V、9–10 +VLED、11 起信号） |')
w('| EDA 排针在 KiCad 无对应 | 18 块板的排针位号 KiCad 中不存在（J20303…J20902），排针级无法对照（芯片级已核对一致） |')
w('| KiCad 有而物理板没有的元件 | 11 个（2 个背板排针、3 个第三排针、下载排针 J4001、扩展排针 J10005、电源/按键排针 J10001–J10004、跳线 JP10001） |')
w('| EDA 新增元件（已按要求忽略） | 电容 + LED 指示模块（LED+三极管+电阻），共 1558 个，逐板清单见 §5 |')
w('| 网络命名差异（不影响连接） | 2 处：B05-1 / B07-1 上 KiCad 的 `data0` 在 EDA 中标为 `data4` |')
w('')
w('## 3. 系统性差异')
w('')
w('### 3.1 背板排针全面重映射（28 块板）')
w('')
w('凡 EDA 排针位号在 KiCad 中存在（J20001、J20101、J20201–J20208、J20301/J20302、J20401/J20402、J20501/J20502、J20601/J20602、J20701/J20702、J20801/J20802、J20901、J21001/J21002、J21101–J21103）的板，排针引脚级差异如下规律：')
w('')
w('- **封装**：KiCad `PinHeader_2x20_P2.54mm`（40 脚）→ EDA `X6522WV-2x32H`（64 脚）。')
w('- **电源脚**：KiCad `+5V`=1–4、`+3V3`=5–8、`GND`=9–14 → EDA `GND`=1–4、`+5V`=5–8、`+VLED`=9–10（EDA 无 +3V3；KiCad 无 +VLED）。')
w('- **信号脚**：KiCad 15 脚起 vs EDA 11 脚起，逐一错位；EDA 还把大量本板不用的系统总线信号（addr0–15、h_a0–15、fc/p1/p2 handshake 等）也分配到排针空脚上，KiCad 中这些脚悬空。')
w('- **GND 扩展**：EDA 排针 44–64 脚全部接 GND（KiCad 40P 无这些脚）。')
w('每块板的完整引脚级对照表见 §5 对应板卡。')
w('')
w('### 3.2 EDA 排针无 KiCad 参照（18 块板）')
w('')
w('下列板的排针位号在 KiCad 系统网表中不存在（KiCad 对应分组只布置了 1–3 个排针，而物理板拆分数量更多）：')
w('')
w('| 板卡 | EDA 排针 | KiCad 该组现有排针 |')
w('|---|---|---|')
w('| B04-3 / B04-4 / B04-5 / B04-6 | J20303 / J20304 / J20305 / J20306 | 仅 J20301、J20302 |')
w('| B06-3 / B06-4 / B06-5 / B06-6 / B06-7 | J20503 / J20504 / J20505 / J20506 / J20507 | 仅 J20501、J20502 |')
w('| B08-3 / B08-4 / B08-5 / B08-6 | J20703 / J20704 / J20705 / J20706 | 仅 J20701、J20702 |')
w('| B09-3 / B09-4 / B09-5 / B09-6 | J20803 / J20804 / J20805 / J20806 | 仅 J20801、J20802 |')
w('| B10-2 | J20902 | 仅 J20901 |')
w('')
w('这些板的**芯片级连接已逐引脚核对，与 KiCad 完全一致**（差异为 0）；但排针本身的网络分配没有 KiCad 参照可对照，无法判定对错。')
w('')
w('### 3.3 B12 组芯片级差异（真实电气差异）')
w('')
w('#### B12-1_HOSTIO：3 个 LED 极性接反 + 晶振引脚编号不同')
w('')
w('**LED 极性接反**（KiCad：2 脚→限流电阻→LED_NET，1 脚→GND；EDA：1 脚→限流电阻→LED_NET，2 脚→GND）：')
w('')
w('| LED 位号 | 网络 | KiCad 连接 | EDA 连接 |')
w('|---|---|---|---|')
w('| D10001（pwr） | LED_PWR | D10001-2=LED_PWR，D10001-1=GND | D10001-1=LED_PWR，D10001-2=GND |')
w('| D10006（image_ready） | LED_IMAGE_READY | D10006-2=LED_IMAGE_READY，D10006-1=GND | D10006-1=LED_IMAGE_READY，D10006-2=GND |')
w('| D10007（model_ready） | LED_MODEL_READY | D10007-2=LED_MODEL_READY，D10007-1=GND | D10007-1=LED_MODEL_READY，D10007-2=GND |')
w('')
w('**X10001（8MHz 晶振 ACH-8.000MHZ-EK）封装引脚编号不同**：')
w('')
w('| 功能 | KiCad（ASE-4P，脚 1–4） | EDA（OSC-TH_4P，DIP 编号） |')
w('|---|---|---|')
w('| +5V | 脚 1、脚 4 | 脚 1、脚 8 |')
w('| GND | 脚 2 | 脚 4 |')
w('| OSC_OUT（时钟输出） | 脚 3 | 脚 5 |')
w('')
w('EDA 上 X10001-2、X10001-3 不存在（即 KiCad 的 GND/OSC_OUT 脚位在 EDA 中无对应脚），X10001-5、X10001-8 为 EDA 多出。功能等价（VCC/GND/OUT 各就各位），但引脚编号体系完全不同。')
w('')
w('#### B12-2_HOSTIO：4 个 LED 极性接反')
w('')
w('| LED 位号 | 网络 |')
w('|---|---|')
w('| D10002（busy） | LED_BUSY |')
w('| D10003（done） | LED_DONE |')
w('| D10004（result_valid） | LED_RESULT_VALID |')
w('| D10005（error） | LED_ERROR |')
w('')
w('极性方向与 B12-1 相同（KiCad 2 脚接电阻侧 / EDA 1 脚接电阻侧）。')
w('')
w('### 3.4 KiCad 有、44 块物理板上都没有的元件（11 个）')
w('')
w('| 位号 | 说明 | KiCad 图页 | 已连接脚数 |')
w('|---|---|---|---|')
for ref, (desc, sheet, np) in kicad_only_meta.items():
    w('| %s | %s | %s | %d |' % (ref, desc, sheet, np))
w('')
w('即：B12 的电源输入/START/RESET/外部时钟 4 个小排针、时钟选择跳线 JP10001、扩展排针 J10005（2×32，H_A0–H_A15 主机地址总线）在 EDA 物理板上都没有对应器件；B01/B05/B07/B11 的第 2/第 3 块背板排针（J20002、J20403、J20603、J21003）以及 B03 的下载排针 J4001 也未落到任何物理板。')
w('')
w('## 4. EDA 后加元件（按用户要求忽略，全部列出备查）')
w('')
w('- **去耦电容**：C*，KiCad 原图带 260 个 C，EDA 板上另有新增。')
w('- **LED 指示模块**：EDA 新增 `LED*+Q*（三极管驱动）+R*（限流）` 组合，每板 1–47 组不等。')
w('- **测试点**：KiCad 有 36 个 TP*，EDA 物理板未放置（重建时刻意排除），两侧均忽略。')
w('- **位号冲突警告**：EDA 新增元件复用了 KiCad 中**其它板**的位号，跨板同名：B04-1/B04-4 上的 R4001–R4008（KiCad 中属 B03 的 10k 上拉排阻位号，EDA 上实为 +VLED 的 LED 限流电阻）、B10-1/B10-2 上的 R10001–R10022（KiCad 中属 B12）。同板内无冲突，不参与比对，但如后续做全系统合并需注意。')
w('')

w('## 5. 逐板明细')
w('')
w('图例：`排针重映射` = 该板排针与 KiCad 同位号排针的引脚级差异（完整表）；`无KiCad参照` = 排针位号 KiCad 不存在；`芯片级差异` = SIGNAL 类差异数。')


def fmt_net(n):
    return '—' if n is None else '`%s`' % n


for board in order:
    e = by.get(board)
    if e is None:
        continue
    w('')
    w('### %s' % board)
    if e.get('status') == 'NO_KICAD_COUNTERPART':
        w('')
        w(e.get('note', ''))
        w('')
        continue
    mc = e.get('mismatch_by_class', {})
    added = e.get('eda_added_components', {})
    added_total = sum(len(v) for v in added.values())
    conn_refs = sorted(e.get('connector_diffs', {}).keys())
    unmatched = e.get('unmatched_eda_connectors', {})
    w('')
    w('- 芯片级差异（SIGNAL）：**%d**　排针分接差异（CONN_TAP）：%d　排针引脚差异（CONN_PIN）：%d' %
      (mc.get('SIGNAL', 0), mc.get('CONN_TAP', 0), mc.get('CONN_PIN', 0)))
    w('- 缺失引脚（KiCad 有 EDA 无）：%d　多余引脚（EDA 有 KiCad 无）：%d' %
      (len(e.get('only_kicad_pins', [])), len(e.get('only_eda_pins', []))))
    w('- 新增（忽略）元件：%d 个 %s' % (added_total, '，'.join('%s×%d' % (k, len(v)) for k, v in sorted(added.items()))))
    if e.get('designator_collisions'):
        w('- ⚠️ 位号冲突（新增元件复用其它板位号）：%s' %
          '，'.join('%s(KiCad 属 %s)' % (r, v['kiCad_on_board']) for r, v in e['designator_collisions'].items()))
    for cref, cd in sorted(e.get('connector_diffs', {}).items()):
        rows = cd['pin_diffs']
        knone = sum(1 for r in rows if r['kicad_net'] is None)
        enone = sum(1 for r in rows if r['eda_net'] is None)
        w('')
        w('**排针 %s 引脚级差异**（共 %d 脚位有差异；KiCad 侧悬空 %d 脚、EDA 侧悬空 %d 脚；KiCad 独有网络：%s；EDA 独有网络：%s）' %
          (cref, len(rows), knone, enone,
           '、'.join(cd['kicad_only_nets']) or '无',
           '、'.join(cd['eda_only_nets']) or '无'))
        w('')
        w('| 脚 | KiCad 网络 | EDA 网络 |')
        w('|---|---|---|')
        for r in rows:
            w('| %s | %s | %s |' % (r['pin'], fmt_net(r['kicad_net']), fmt_net(r['eda_net'])))
    for cref, info in sorted(unmatched.items()):
        w('')
        w('**排针 %s**：KiCad 中不存在（%d 脚接入 %d 个网络），无参照，未做引脚级对照。' %
          (cref, info['pins_in_nets'], info['nets']))
    # chip-level detail
    sig = [m for m in e.get('mismatches', []) if m['class'] == 'SIGNAL']
    if sig:
        w('')
        w('**芯片级差异明细（%d 处）**：' % len(sig))
        w('')
        w('| 引脚 | KiCad 网络 | KiCad 分区 | EDA 网络 | EDA 分区 |')
        w('|---|---|---|---|---|')
        for m in sig:
            w('| %s | %s | %s | %s | %s |' % (
                m['pin'], fmt_net(m['kicad_net'].rsplit('/', 1)[-1]),
                ' '.join(m['kicad_peers']), fmt_net(m['eda_net'].rsplit('/', 1)[-1]),
                ' '.join(m['eda_peers'])))
    if e.get('only_kicad_pins'):
        w('')
        w('**KiCad 有而 EDA 缺失的引脚**：%s' % '、'.join(e['only_kicad_pins']))

w('')
w('## 6. 附录')
w('')
w('- EDA 逐页网表：`netlist_compare_v2/jlc_netlists/<板名>__<页名>.net`（Protel2 格式，93 页，导出 0 失败）')
w('- KiCad 参照网表：`netlist_compare_v2/kicad/kicad_system.net`（kicadsexpr，由 `Cache/CNN_74xx_System` 导出）')
w('- 比对脚本：`netlist_compare_v2/scripts/export_jlc_netlists.mjs`（经 easyeda-bridge 自动导出）、`compare_strict.py`（分区比对）、`gen_report.py`（本报告）')
w('- 机器可读结果：`netlist_compare_v2/results/compare_raw.json`')
w('- 说明：KiCad 导出时有“批注错误”警告，但网表中 1315 个位号无重复，不影响比对；EDA 网表导出为板级（同板多页导出结果一致）。')
w('- B13_LUT_REF（S_LUT_Mult_1）不在 KiCad 系统工程根图内，无参照网表，未比对。')

open(os.path.abspath(OUT), 'w', encoding='utf-8').write('\n'.join(L))
print('report written:', os.path.abspath(OUT), len('\n'.join(L)), 'chars')
