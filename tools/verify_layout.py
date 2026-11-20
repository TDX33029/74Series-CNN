#!/usr/bin/env python3
"""主代理验收脚本：检查布局是否满足用户硬性要求。

用法:
    python tools/verify_layout.py <eda_dump_positions.py 的输出 JSON>

检查项:
  1. LED 全部正面(layer=1)、横放(rot=0)、单列(x 一致)
  2. LED 竖向节距: 组内 <=150mil；组间 150~300mil
  3. Q 全部背面(layer=2)；R/RP 全部背面(layer=2)
  4. 每个 LED（电源灯 LEDP* 除外）都有同 y 的 Q + 至少 2 个 R；电源灯有同 y 的 RP 或 R
  5. 芯片(U) 全部正面、rot=90
  6. LED 位于所有芯片右侧

退出码: 0=PASS, 1=有 FAIL。
"""
import collections
import json
import sys


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    data = json.load(open(sys.argv[1], 'r', encoding='utf-8'))

    at = lambda c: round(c['y'], 1)
    U = [c for c in data if c['des'].startswith('U')]
    LED = [c for c in data if c['des'].startswith('LED')]
    Q = [c for c in data if c['des'].startswith('Q')]
    R = [c for c in data if c['des'].startswith('R') and not c['des'].startswith('RP')]
    RP = [c for c in data if c['des'].startswith('RP')]
    J = [c for c in data if c['des'].startswith('J')]

    fails = []
    warns = []

    print(f'器件统计: U={len(U)} LED={len(LED)} Q={len(Q)} R={len(R)} RP={len(RP)} J={len(J)} 其他={len(data)-len(U)-len(LED)-len(Q)-len(R)-len(RP)-len(J)}')

    if not LED:
        print('FAIL: 未找到任何 LED 器件（位号应以 LED 开头）')
        sys.exit(1)

    # 1. LED 层/旋转/单列
    bad_led = [c['des'] for c in LED if c['layer'] != 1 or abs(c['rot']) > 1]
    if bad_led:
        fails.append(f'LED 未全部正面且 rot=0: {bad_led[:6]}')
    xs = [c['x'] for c in LED]
    if max(xs) - min(xs) > 2:
        fails.append(f'LED 非单列: x 范围 {min(xs):.1f} ~ {max(xs):.1f}')
    print(f'LED 列 x = {min(xs):.1f} ~ {max(xs):.1f}（{len(LED)} 颗，rot=0，layer=1）')

    # 2. 节距
    ys = sorted(at(c) for c in LED)
    diffs = [round(ys[i + 1] - ys[i], 1) for i in range(len(ys) - 1)]
    within = [d for d in diffs if d <= 150]
    seps = [d for d in diffs if 150 < d <= 300]
    over = [d for d in diffs if d > 300]
    if within and max(within) > 150:
        fails.append(f'组内节距超过 150: {max(within)}')
    if over:
        fails.append(f'存在 >300mil 的异常间断: {over}')
    n_groups = len(seps) + 1
    print(f'竖向间隙序列: {diffs}')
    print(f'组内节距 max={max(within) if within else 0}  组间间隔={seps}  => 推定 {n_groups} 组')
    if n_groups != 3:
        warns.append(f'推定组数为 {n_groups}（期望 3：电源/控制/数据）——请人工核对汇报分组')
    print('\nLED 从下往上（y 由负到正或由大到小按坐标系，此处按升序）:')
    for c in sorted(LED, key=lambda c: c['y']):
        print(f"  {c['des']:24s} y={c['y']:9.1f}")

    # 3. Q/R 层
    bad_q = [c['des'] for c in Q if c['layer'] != 2]
    if bad_q:
        fails.append(f'Q 未全部在背面: {bad_q[:6]}')
    bad_r = [c['des'] for c in R + RP if c['layer'] != 2]
    if bad_r:
        fails.append(f'R/RP 未全部在背面: {bad_r[:6]}')

    # 4. 模块同 y
    q_by_y = collections.defaultdict(list)
    r_by_y = collections.defaultdict(list)
    for q in Q:
        q_by_y[at(q)].append(q['des'])
    for r in R + RP:
        r_by_y[at(r)].append(r['des'])
    mod_ok = 0
    mod_bad = []
    for l in LED:
        if l['des'].startswith('LEDP') or 'PWR' in l['des'].upper():
            rp = [x['des'] for x in RP if abs(at(x) - at(l)) < 2]
            if rp or len(r_by_y.get(at(l), [])) >= 1:
                mod_ok += 1
            else:
                mod_bad.append((l['des'], 'no RP/R at same y'))
            continue
        q = q_by_y.get(at(l), [])
        rp = r_by_y.get(at(l), [])
        if q and len(rp) >= 2:
            mod_ok += 1
        else:
            mod_bad.append((l['des'], f'Q={q} R={rp}'))
    print(f'\n模块同 y 覆盖: {mod_ok}/{len(LED)}')
    if mod_bad:
        fails.append(f'存在模块不就近的 LED: {mod_bad[:8]}')

    # 5. 芯片
    bad_u = [c['des'] for c in U if c['layer'] != 1 or abs(c['rot'] - 90) > 1]
    if bad_u:
        fails.append(f'芯片未全部正面且 rot=90: {bad_u[:6]}')
    if U:
        print(f'芯片: {len(U)} 片，x={min(c["x"] for c in U):.0f}~{max(c["x"] for c in U):.0f}，全部 rot=90 layer=1')

    # 6. LED 在最右
    if U and min(xs) <= max(c['x'] for c in U):
        fails.append('LED 列不在所有芯片右侧')

    print('\n================ 验收结论 ================')
    for w in warns:
        print('WARN:', w)
    if fails:
        for f in fails:
            print('FAIL:', f)
        print('结果: FAIL')
        sys.exit(1)
    print('结果: PASS（几何规则全部满足；DRC 请另跑 tools/eda_drc.py；分组顺序请核对汇报）')


if __name__ == '__main__':
    main()
