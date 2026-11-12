#!/usr/bin/env python3
"""Strict netlist connectivity comparison: 74CNN-BRD (EasyEDA, per-board Protel2 exports)
vs CNN_74xx_System (KiCad kicadsexpr global netlist).

Method: pin-partition equivalence. Two pins are equivalent iff they belong to the same
net. For every common pin, the restricted partition (net pin-set intersected with the
board's component pins) must be identical on both sides. Net names are ignored
(hierarchical prefixes differ); unconnected-* pseudo nets are skipped.

Ignored per user request (后加元素): capacitors (C*), LEDs (LED*/D*), test points (TP*)
on BOTH sides, plus KiCad root power flags (FLG*). EDA-only components are auto-detected
and reported; they are excluded from partition comparison but listed in the report.
"""
import json
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KICAD_NET = os.path.join(BASE, 'kicad', 'kicad_system.net')
JLC_DIR = os.path.join(BASE, 'jlc_netlists')
BOARDS_JSON = os.path.join(BASE, 'boards_pages.json')
OUTDIR = os.path.join(BASE, 'results')

# refs ignored on BOTH sides (user: ignore caps / LEDs / etc. added later; test points
# were deliberately excluded from the physical boards)
IGNORE_RE = re.compile(r'^(C|LED|TP)\d+', re.I)
# KiCad root-sheet power flags (ERC artifacts, not physical parts)
KICAD_EXTRA_IGNORE_RE = re.compile(r'^FLG\d', re.I)
POWER_NET_RE = re.compile(r'^\+?[0-9]*V[A-Z0-9]*$|^GND$|^AGND$|^PGND$', re.I)


def parse_kicad(path):
    s = open(path, encoding='utf-8').read()
    comps = {}
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)(.*?)\n\t\t\)', s, re.S):
        ref, body = m.group(1), m.group(2)
        val = re.search(r'\(value "([^"]*)"\)', body)
        fp = re.search(r'\(footprint "([^"]*)"\)', body)
        sp = re.search(r'\(names "([^"]*)"\)', body)
        comps[ref] = {
            'value': val.group(1) if val else '',
            'footprint': fp.group(1) if fp else '',
            'sheet': sp.group(1) if sp else '/',
        }
    nets = {}
    for m in re.finditer(r'\(net\s+\(code "[^"]*"\)\s+\(name "([^"]*)"\)(.*?)\n\t\t\)', s, re.S):
        name = m.group(1)
        if name.startswith('unconnected-') or name.startswith('unconnected_'):
            continue
        pins = set()
        for n in re.finditer(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
            pins.add((n.group(1), n.group(2)))
        if pins:
            nets[name] = pins
    return comps, nets


def parse_protel(path):
    """Return (comps, nets). comps: ref -> {footprint, parttype}; nets: name -> set((ref,pin))."""
    lines = open(path, encoding='utf-8').read().replace('\r\n', '\n').replace('\r', '\n').splitlines()
    comps = {}
    nets = {}
    i = 0
    n = len(lines)
    unnamed = 0
    while i < n:
        ln = lines[i].strip()
        if ln == '[':
            # component block: label/value pairs (DESIGNATOR, FOOTPRINT, PARTTYPE, ...)
            j = i + 1
            fields = {}
            while j < n and lines[j].strip() != ']':
                t = lines[j].strip()
                if t == 'DESIGNATOR' and j + 1 < n:
                    fields['ref'] = lines[j + 1].strip()
                    j += 1
                elif t == 'FOOTPRINT' and j + 1 < n:
                    fields['footprint'] = lines[j + 1].strip()
                    j += 1
                elif t == 'PARTTYPE' and j + 1 < n:
                    fields['parttype'] = lines[j + 1].strip()
                    j += 1
                j += 1
            if 'ref' in fields:
                comps[fields['ref']] = {'footprint': fields.get('footprint', ''),
                                        'parttype': fields.get('parttype', '')}
            i = j + 1
            continue
        if ln == '(':
            j = i + 1
            name = lines[j].strip() if j < n else ''
            if not name:
                name = '$UNNAMED_%d' % unnamed
                unnamed += 1
            pins = set()
            j += 1
            while j < n and lines[j].strip() != ')':
                tok = lines[j].split()[0] if lines[j].split() else ''
                if '-' in tok:
                    ref, pin = tok.split('-', 1)
                    pins.add((ref, pin))
                j += 1
            if pins:
                if name in nets and (nets[name] & pins):
                    # same name, overlapping pin sets on different page exports:
                    # EasyEDA merges same-name nets across pages (Update-PCB semantics)
                    nets[name] |= pins
                elif name in nets:
                    # same auto-name on different pages with disjoint pins = different nets
                    k = 2
                    while ('%s#%d' % (name, k)) in nets:
                        k += 1
                    nets['%s#%d' % (name, k)] = pins
                else:
                    nets[name] = pins
            i = j
            i += 1
            continue
        i += 1
    return comps, nets


def norm_name(name):
    n = name.rsplit('/', 1)[-1] if '/' in name else name
    return n.casefold()


def kicad_logical_board(sheet):
    """Logical board prefix from a KiCad sheet instance path: /B03_S04_Memories/ -> B03.
    Root '/' or non-board sheets -> None (system-level)."""
    seg = sheet.strip('/').split('/')[0] if sheet and sheet != '/' else ''
    m = re.match(r'^(B\d{2})_', seg)
    return m.group(1) if m else None


def eda_logical_board(board_name):
    m = re.match(r'^(B\d{2})[-_]', board_name + '-')
    return m.group(1) if m else None


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    kcomps, knets = parse_kicad(KICAD_NET)
    boards = json.load(open(BOARDS_JSON, encoding='utf-8'))['result']

    # group EDA page exports per board
    board_pages = {b['board']: [p['name'] for p in b['pages']] for b in boards}
    board_files = defaultdict(list)
    for f in os.listdir(JLC_DIR):
        if not f.endswith('.net'):
            continue
        board, page = f[:-4].split('__', 1)
        board_files[board].append((page, os.path.join(JLC_DIR, f)))

    board_nets = {}
    board_comps = {}
    board_pages_parsed = {}
    for board, files in board_files.items():
        nets = {}
        comps = {}
        parsed_pages = {}
        for page, path in sorted(files):
            c, n = parse_protel(path)
            parsed_pages[page] = (len(c), len(n))
            comps.update(c)
            for name, pins in n.items():
                if name in nets:
                    nets[name] |= pins
                else:
                    nets[name] = pins
        board_nets[board] = nets
        board_comps[board] = comps
        board_pages_parsed[board] = parsed_pages

    def ign(ref):
        return bool(IGNORE_RE.match(ref))

    def kign(ref):
        return bool(IGNORE_RE.match(ref) or KICAD_EXTRA_IGNORE_RE.match(ref))

    report = []
    seen_kicad_refs = defaultdict(list)   # kicad ref -> boards containing it
    kicad_all_refs = set(kcomps)

    for board in sorted(board_files):
        if board not in board_nets:
            continue
        entry = {'board': board}
        if board == 'B13_LUT_REF':
            entry['status'] = 'NO_KICAD_COUNTERPART'
            entry['note'] = 'S_LUT_Mult_1 不在 KiCad 系统工程根图中，无参照网表'
            report.append(entry)
            continue
        enets = board_nets[board]
        ecomps = board_comps[board]
        erefs = set(ecomps)
        lb = eda_logical_board(board)

        # refs in this board's netlist whose KiCad counterpart lives on a DIFFERENT
        # logical board = designator collision with an added element (e.g. LED series
        # resistor R4001 reusing B03's pullup ref) -> treat as EDA-added, flag it
        collision_refs = {}
        for r in erefs:
            if r in kicad_all_refs:
                klb = kicad_logical_board(kcomps[r]['sheet'])
                if lb and klb and klb != lb:
                    collision_refs.setdefault(r, klb)
        # EDA-only components = elements added to EasyEDA after the KiCad reference
        # (decoupling caps, power LEDs + driver transistors + series resistors ...).
        # They are excluded from the comparison per user request, but listed in full.
        eda_only = sorted(r for r in erefs if r not in kicad_all_refs or r in collision_refs)
        board_refs = {r for r in erefs
                      if r in kicad_all_refs and r not in collision_refs and not ign(r)}

        def ctype(ref):
            m = re.match(r'^([A-Za-z]+)', ref)
            return m.group(1) if m else '?'

        eda_only_by_type = defaultdict(list)
        for r in eda_only:
            eda_only_by_type[ctype(r)].append(r)        # duplicate detection across boards
        for r in board_refs:
            seen_kicad_refs[r].append(board)

        # EDA pin map (skip EDA's own UNCONNECTED-* single-pin pseudo nets)
        epin_net = {}
        multi_net_pins = []
        for name, pins in enets.items():
            if name.upper().startswith('UNCONNECTED-') or name.upper().startswith('UNCONNECTED_'):
                continue
            for p in pins:
                if p[0] in board_refs:
                    if p in epin_net:
                        multi_net_pins.append('%s-%s' % p)
                    else:
                        epin_net[p] = name

        # KiCad pin map restricted to this board's refs
        kpin_net = {}
        for name, pins in knets.items():
            for p in pins:
                if p[0] in board_refs:
                    kpin_net[p] = name

        common = set(kpin_net) & set(epin_net)
        only_k = sorted(set(kpin_net) - set(epin_net))
        only_e = sorted(set(epin_net) - set(kpin_net))

        conn_refs = {r for r in board_refs if r.startswith('J')}

        def is_conn_pin(p):
            return p[0] in conn_refs

        mism = []
        for p in sorted(common):
            kp = knets[kpin_net[p]]
            ep = enets[epin_net[p]]
            ks = frozenset(q for q in kp if q[0] in board_refs)
            es = frozenset(q for q in ep if q[0] in board_refs)
            if ks != es:
                kd = ks - es
                ed = es - ks
                # classify: connector-level when the pin or every differing peer is a
                # connector pin; SIGNAL only when chip-to-chip wiring differs
                if is_conn_pin(p):
                    cls = 'CONN_PIN'
                elif kd | ed and all(is_conn_pin(q) for q in kd | ed):
                    cls = 'CONN_TAP'
                else:
                    cls = 'SIGNAL'
                mism.append({
                    'pin': '%s-%s' % p,
                    'class': cls,
                    'kicad_net': kpin_net[p],
                    'kicad_peers': sorted('%s-%s' % q for q in ks),
                    'eda_net': epin_net[p],
                    'eda_peers': sorted('%s-%s' % q for q in es),
                })

        # connector pin-map diff (net-name based, for readable remap tables)
        conn_diff = {}
        for cref in sorted(conn_refs):
            kmap = {pin: norm_name(net) for (ref, pin), net in kpin_net.items() if ref == cref}
            emap = {pin: norm_name(net) for (ref, pin), net in epin_net.items() if ref == cref}
            rows = []
            for pin in sorted(set(kmap) | set(emap), key=lambda x: (len(x), x)):
                kn = kmap.get(pin)
                en = emap.get(pin)
                if kn != en:
                    rows.append({'pin': pin, 'kicad_net': kn, 'eda_net': en})
            # nets present on both sides' connector but on different pins
            krev = defaultdict(list)
            erev = defaultdict(list)
            for pin, net in kmap.items():
                krev[net].append(pin)
            for pin, net in emap.items():
                erev[net].append(pin)
            shared = set(krev) & set(erev)
            remapped = {n: (sorted(krev[n]), sorted(erev[n])) for n in shared
                        if sorted(krev[n]) != sorted(erev[n])}
            konly_nets = sorted(set(krev) - set(erev))
            eonly_nets = sorted(set(erev) - set(krev))
            if rows or remapped or konly_nets or eonly_nets:
                conn_diff[cref] = {'pin_diffs': rows, 'remapped_nets': remapped,
                                   'kicad_only_nets': konly_nets, 'eda_only_nets': eonly_nets}

        # net-name mapping check (informational only): common partition, different label
        name_diffs = []
        k_by_fs = {}
        for name, pins in knets.items():
            fs = frozenset(q for q in pins if q[0] in board_refs)
            if fs:
                k_by_fs[fs] = norm_name(name)
        for name, pins in enets.items():
            fs = frozenset(q for q in pins if q[0] in board_refs)
            if fs and fs in k_by_fs and k_by_fs[fs] and k_by_fs[fs] != norm_name(name):
                name_diffs.append({'kicad': k_by_fs[fs], 'eda': norm_name(name)})

        # connectors present on the EDA board but without a KiCad counterpart ref
        # (KiCad group has fewer connectors than the physical split) -> the connector
        # itself cannot be pin-verified; listed explicitly
        unmatched_conns = {}
        for r in sorted(erefs - board_refs):
            if r.startswith('J'):
                nets_r = [name for name, pins in enets.items() if any(q[0] == r for q in pins)]
                unmatched_conns[r] = {'pins_in_nets': sum(1 for name, pins in enets.items()
                                                          for q in pins if q[0] == r),
                                      'nets': len(nets_r),
                                      'in_kicad': r in kicad_all_refs}

        entry.update({
            'eda_refs': len(erefs),
            'compared_refs': len(board_refs),
            'eda_added_components': {k: v for k, v in sorted(eda_only_by_type.items())},
            'designator_collisions': {r: {'kiCad_on_board': v,
                                          'eda_parttype': ecomps[r].get('parttype', ''),
                                          'kiCad_value': kcomps[r]['value']}
                                      for r, v in sorted(collision_refs.items())},
            'multi_net_pins_eda': sorted(set(multi_net_pins)),
            'common_pins': len(common),
            'only_kicad_pins': ['%s-%s' % p for p in only_k],
            'only_eda_pins': ['%s-%s' % p for p in only_e],
            'mismatch_count': len(mism),
            'mismatch_by_class': {
                'SIGNAL': sum(1 for m in mism if m['class'] == 'SIGNAL'),
                'CONN_TAP': sum(1 for m in mism if m['class'] == 'CONN_TAP'),
                'CONN_PIN': sum(1 for m in mism if m['class'] == 'CONN_PIN'),
            },
            'mismatches': mism,
            'connector_diffs': conn_diff,
            'unmatched_eda_connectors': unmatched_conns,
            'net_name_diffs': name_diffs,
        })
        ok = (not mism and not only_k and not only_e and not conn_diff
              and not multi_net_pins and not unmatched_conns)
        entry['status'] = 'PASS' if ok else 'DIFF'
        report.append(entry)

    # global coverage: KiCad comps that should live on exactly one board
    covered = {}
    for r in sorted(kicad_all_refs):
        if kign(r):
            continue
        bs = seen_kicad_refs.get(r, [])
        covered[r] = bs
    missing_refs = {r: v for r, v in covered.items() if len(v) == 0}
    dup_refs = {r: v for r, v in covered.items() if len(v) > 1}

    summary = {
        'kicad_comps': len(kcomps),
        'kicad_nets': len(knets),
        'boards': len(board_files),
        'missing_kicad_components': missing_refs,
        'duplicated_on_multiple_boards': dup_refs,
    }
    json.dump({'summary': summary, 'boards': report},
              open(os.path.join(OUTDIR, 'compare_raw.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # console summary
    npass = sum(1 for e in report if e.get('status') == 'PASS')
    print('KiCad comps=%d nets=%d | boards=%d PASS=%d DIFF=%d' % (
        len(kcomps), len(knets), len(report), npass, len(report) - npass))
    print('missing KiCad comps (on no board):', len(missing_refs))
    print('duplicated comps (on >1 board):', len(dup_refs))
    for e in report:
        if e.get('status') in ('DIFF', 'NO_KICAD_COUNTERPART'):
            mc = e.get('mismatch_by_class', {})
            print('%-18s %s mism=%d(sig=%d conn=%d) onlyK=%d onlyE=%d added=%d' % (
                e['board'], e.get('status'), e.get('mismatch_count', 0),
                mc.get('SIGNAL', 0), mc.get('CONN_PIN', 0) + mc.get('CONN_REMAP', 0),
                len(e.get('only_kicad_pins', [])), len(e.get('only_eda_pins', [])),
                sum(len(v) for v in e.get('eda_added_components', {}).values())))


if __name__ == '__main__':
    main()
