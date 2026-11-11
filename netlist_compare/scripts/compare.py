"""Compare KiCad flattened netlist vs EasyEDA per-board Protel2 netlists.

- Boards B01..B12: KiCad sheet-prefix groups vs EasyEDA board netlists.
- EasyEDA-added LED modules (extra components) are removed before comparing.
- Net names compared case-insensitively; pinset fallback matching detects renames,
  merges and splits.
- B13_LUT_REF reported separately (no KiCad counterpart in system netlist).
- B00_BASIC_LED is EasyEDA-only and ignored entirely.
"""
import sys, os, re, json
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, children, child, val, fields

BASE = r"D:\Document\tempPrj\74Series-CNN\netlist_compare"
JDIR = os.path.join(BASE, 'jlc_netlists')

BOARD_SHEETS = {
    'B01_SUPERVISOR': ['B01_S01_Supervisor', 'B01_Conn'],
    'B02_TIMING':     ['B02_S02_Timing', 'B02_Conn'],
    'B03_MEMORY':     ['B03_S04_Memories', 'B03_Conn'],
    'B04_CONV1':      ['B04_S07_Conv1', 'B04_S13_Requant_C1', 'B04_Conn'],
    'B05_POOL1':      ['B05_S05_Pool1', 'B05_S12A_PoolLatch1', 'B05_Conn'],
    'B06_CONV2':      ['B06_S08_Conv2', 'B06_S15_Requant_C2', 'B06_Conn'],
    'B07_POOL2':      ['B07_S05_Pool2', 'B07_S12A_PoolLatch2', 'B07_Conn'],
    'B08_FC1':        ['B08_S09_FC1', 'B08_S17_FC1', 'B08_Conn'],
    'B09_FC2':        ['B09_S09_FC2', 'B09_S17_FC2', 'B09_Conn'],
    'B10_ARGMAX':     ['B10_S06_Argmax', 'B10_S12B_ScoreLatch', 'B10_Conn'],
    'B11_BUSFAB':     ['B11_S11_BusFabric', 'B11_S11A_EngineMerge', 'B11_Conn'],
    'B12_HOSTIO':     ['B12_S10_Top_IO', 'B12_Conn'],
}

# ---------- parse KiCad ----------
root = parse(open(os.path.join(BASE, 'kicad_net.net'), encoding='utf-8').read())[0]
comps_sec = child(root, 'components')
nets_sec = child(root, 'nets')

kicad_comps = {}      # ref -> sheetpath-names
kicad_comp_meta = {}  # ref -> dict(value, footprint, part, desc)
for c in children(comps_sec, 'comp'):
    ref = val(c, 'ref')
    sp = child(c, 'sheetpath')
    names = val(sp, 'names') if sp is not None else '/'
    fl = fields(c)
    ls = child(c, 'libsource')
    kicad_comps[ref] = names
    kicad_comp_meta[ref] = {
        'value': val(c, 'value'),
        'footprint': fl.get('Footprint', ''),
        'part': val(ls, 'part') if ls is not None else '',
    }

kicad_nets = {}       # raw name -> set((ref,pin))
for n in children(nets_sec, 'net'):
    name = val(n, 'name')
    pins = set()
    for nd in children(n, 'node'):
        pins.add((val(nd, 'ref'), str(val(nd, 'pin'))))
    kicad_nets[name] = pins

# ---------- parse EasyEDA Protel2 ----------
def parse_protel(text):
    """Returns (comps, nets). comps: designator -> {footprint, parttype}
    nets: netname -> [(designator, pin)]
    Component record: '[' DESIGNATOR <des> FOOTPRINT <fp> PARTTYPE <pt> ... '*' ']'
    Net record: '(' <netname> <pin-line>* ')' where each pin line starts with '<des>-<pin>'."""
    lines = text.replace('\r\n', '\n').split('\n')
    comps, nets = {}, {}
    i = 0
    n = len(lines)
    while i < n:
        if lines[i] == '[':
            j = lines.index(']', i)
            block = lines[i + 1:j]
            if block and block[-1] == '*':
                block = block[:-1]
            if len(block) >= 5:
                des, fp, pt = block[1], block[3], block[5]
                if des != 'DESIGNATOR':
                    comps.setdefault(des, {'footprint': fp, 'parttype': pt})
            i = j + 1
        elif lines[i] == '(':
            j = lines.index(')', i)
            block = lines[i + 1:j]
            if len(block) >= 2:
                name = block[0].strip()
                pins = []
                for line in block[1:]:
                    tok = line.split()[0] if line.split() else ''
                    m = re.match(r'^(.+)-(\w+)$', tok)
                    if m:
                        pins.append((m.group(1), m.group(2)))
                nets.setdefault(name, []).extend(pins)
            i = j + 1
        else:
            i += 1
    return comps, nets

easy = {}
for fn in os.listdir(JDIR):
    if not fn.endswith('.net'):
        continue
    board = fn[:-4]
    easy[board] = parse_protel(open(os.path.join(JDIR, fn), encoding='utf-8').read())

report = {}
all_added = {}
all_missing = {}
issues = 0

def added_ok_check(r):
    # a board is clean if: no pin diffs, no pinset diffs, no unmatched nets
    return (r['n_pins_only_kicad'] or r['n_pins_only_easyeda'] or
            r['n_nets_pinset_diff'] or r['n_nets_only_kicad'] or r['n_nets_only_easyeda'])

for board, sheets in BOARD_SHEETS.items():
    r = {'board': board}
    # KiCad per-board comps
    comps_k = {ref for ref, path in kicad_comps.items()
               if any(seg in sheets for seg in path.strip('/').split('/'))}
    comps_e = set(easy[board][0].keys())

    added = sorted(comps_e - comps_k)
    missing = sorted(comps_k - comps_e)
    r['added_comps'] = added
    r['missing_comps'] = missing
    all_added[board] = added
    all_missing[board] = missing

    # EasyEDA nets minus added comps' pins
    nets_e = {}
    for name, pins in easy[board][1].items():
        kept = [(d, p) for (d, p) in pins if d not in set(added)]
        if kept:
            nets_e[name] = set(kept)

    # KiCad nets restricted to board comps
    nets_k = {}
    for name, pins in kicad_nets.items():
        kept = {(d, p) for (d, p) in pins if d in comps_k}
        if kept:
            nets_k[name] = kept

    # --- pin inventory diff (only pins that appear in nets) ---
    pins_k = {}
    for name, pins in nets_k.items():
        for pin in pins:
            pins_k[pin] = name
    pins_e = {}
    for name, pins in nets_e.items():
        for pin in pins:
            pins_e[pin] = name
    pins_k_only = sorted(pins_k.keys() - pins_e.keys())
    pins_e_only = sorted(pins_e.keys() - pins_k.keys())
    r['pins_only_kicad'] = [f'{d}-{p}' for d, p in pins_k_only][:60]
    r['pins_only_easyeda'] = [f'{d}-{p}' for d, p in pins_e_only][:60]
    r['n_pins_only_kicad'] = len(pins_k_only)
    r['n_pins_only_easyeda'] = len(pins_e_only)

    # --- net name matching (casefold) ---
    nk = defaultdict(list)
    for name in nets_k:
        nk[name.casefold()].append(name)
    ne = defaultdict(list)
    for name in nets_e:
        ne[name.casefold()].append(name)
    common = sorted(set(nk) & set(ne))
    k_only = sorted(set(nk) - set(ne))
    e_only = sorted(set(ne) - set(nk))

    matched_ok, pinset_diff = [], []
    for cf in common:
        # if duplicate casefold variants, treat all
        kpin = set()
        for name in nk[cf]:
            kpin |= nets_k[name]
        epin = set()
        for name in ne[cf]:
            epin |= nets_e[name]
        if kpin == epin:
            matched_ok.append(cf)
        else:
            pinset_diff.append((cf, sorted(nk[cf]), sorted(ne[cf]), kpin, epin))

    # renamed / merged / split detection by exact pinset on remaining
    krem = {}
    for cf in k_only:
        krem[cf] = set().union(*(nets_k[x] for x in nk[cf]))
    erem = {}
    for cf in e_only:
        erem[cf] = set().union(*(nets_e[x] for x in ne[cf]))
    rename_pairs = []
    used_e = set()
    for kf, kp in krem.items():
        exact = [ef for ef, ep in erem.items() if ef not in used_e and ep == kp]
        if exact:
            used_e.add(exact[0])
            rename_pairs.append((kf, exact[0], len(kp)))
    rename_map = {kf: ef for kf, ef, _ in rename_pairs}
    k_unmatched = sorted(set(krem) - set(rename_map))
    e_unmatched = sorted(set(erem) - set(rename_map.values()))

    r['n_nets_kicad'] = len(nets_k)
    r['n_nets_easyeda'] = len(nets_e)
    r['n_nets_matched'] = len(matched_ok)
    r['n_nets_pinset_diff'] = len(pinset_diff)
    r['n_nets_renamed'] = len(rename_pairs)
    r['n_nets_only_kicad'] = len(k_unmatched)
    r['n_nets_only_easyeda'] = len(e_unmatched)
    r['renamed'] = [(kf, ef, n) for kf, ef, n in rename_pairs][:40]
    r['nets_only_kicad'] = [(kf, len(krem[kf]), sorted(krem[kf])[:8]) for kf in k_unmatched][:40]
    r['nets_only_easyeda'] = [(ef, len(erem[ef]), sorted(erem[ef])[:8]) for ef in e_unmatched][:40]
    r['nets_pinset_diff'] = [
        {'casefold': cf, 'kicad_names': kn, 'easyeda_names': en,
         'kicad_only_pins': [f'{d}-{p}' for d, p in sorted(kp - ep)][:15],
         'easyeda_only_pins': [f'{d}-{p}' for d, p in sorted(ep - kp)][:15],
         }
        for cf, kn, en, kp, ep in pinset_diff[:60]
    ]
    report[board] = r
    issues += len(pinset_diff) + len(k_unmatched) + len(e_unmatched) + len(pins_k_only) + len(pins_e_only)

# print summary
print('=' * 100)
for board, r in report.items():
    clean = not added_ok_check(r)
    print(f"{board:16s} K-nets={r['n_nets_kicad']:4d} E-nets={r['n_nets_easyeda']:4d} "
          f"matched={r['n_nets_matched']:4d} renamed={r['n_nets_renamed']:3d} "
          f"pinset-diff={r['n_nets_pinset_diff']:3d} K-only={r['n_nets_only_kicad']:3d} "
          f"E-only={r['n_nets_only_easyeda']:3d} pinsK-only={r['n_pins_only_kicad']:4d} "
          f"pinsE-only={r['n_pins_only_easyeda']:4d} added={len(r['added_comps']):3d} "
          f"missing={len(r['missing_comps']):3d}  -> {'CLEAN' if clean else 'DIFF'}")

json.dump(report, open(os.path.join(BASE, 'report_raw.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\nwritten report_raw.json; total issue units:', issues)

# B13 note
print('\nB13_LUT_REF: EasyEDA-only board (KiCad system does not instantiate S_LUT_Mult_1)')
print('B00_BASIC_LED: ignored per user (LED modules)')
