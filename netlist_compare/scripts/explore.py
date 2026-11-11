"""Explore both netlist sides: KiCad flattened + EasyEDA per-board Protel2."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, children, child, val, props, fields

BASE = r"D:\Document\tempPrj\74Series-CNN\netlist_compare"

# ---------- KiCad ----------
root = parse(open(os.path.join(BASE, 'kicad_net.net'), encoding='utf-8').read())[0]
comps_sec = child(root, 'components')
nets_sec = child(root, 'nets')

kicad_comps = {}   # ref -> {sheetname, sheetpath, footprint, value, desc}
for c in children(comps_sec, 'comp'):
    ref = val(c, 'ref')
    sp = child(c, 'sheetpath')
    names = val(sp, 'names') if sp is not None else '/'
    fl = fields(c)
    ls = child(c, 'libsource')
    kicad_comps[ref] = {
        'sheetname': names,
        'value': val(c, 'value'),
        'desc': val(c, 'description'),
        'footprint': fl.get('Footprint', ''),
        'part': val(ls, 'part') if ls is not None else '',
    }

kicad_nets = {}    # name -> {(ref, pin)}
for n in children(nets_sec, 'net'):
    name = val(n, 'name')
    pins = set()
    for nd in children(n, 'node'):
        pins.add((val(nd, 'ref'), val(nd, 'pin')))
    kicad_nets[name] = pins

# sheet prefix grouping
from collections import defaultdict
by_prefix = defaultdict(list)
for ref, info in kicad_comps.items():
    sn = info['sheetname']
    parts = [p for p in sn.strip('/').split('/') if p]
    prefix = parts[0] if parts else '(top)'
    by_prefix[prefix].append(ref)

print('== KiCad sheet prefixes (components per prefix) ==')
for k in sorted(by_prefix):
    samples = sorted(by_prefix[k])[:6]
    print(f'{k:28s} n={len(by_prefix[k]):5d}  samples={samples}')

led_refs = [r for r in kicad_comps if re.search(r'LED|D\d', r, re.I)]
print('KiCad LED-ish refs:', len(led_refs), led_refs[:20])
print('KiCad nets:', len(kicad_nets))
print('KiCad FLG refs:', [r for r in kicad_comps if r.startswith('FLG')])
# net name styles
auto_nets = [n for n in kicad_nets if n.startswith('Net-')]
print('KiCad auto-nets (Net-*):', len(auto_nets), auto_nets[:8])
hier = [n for n in kicad_nets if n.startswith('/')]
print('KiCad slash-nets:', len(hier), hier[:8])
plain = [n for n in kicad_nets if not n.startswith('/') and not n.startswith('Net-')]
print('KiCad plain nets:', len(plain), plain[:8])

# ---------- EasyEDA ----------
print()
print('== EasyEDA boards ==')
jdir = os.path.join(BASE, 'jlc_netlists')
for fn in sorted(os.listdir(jdir)):
    t = open(os.path.join(jdir, fn), encoding='utf-8').read()
    comps = re.findall(r'\[\r?\nDESIGNATOR\r?\n(.*?)\r?\nFOOTPRINT\r?\n(.*?)\r?\nPARTTYPE\r?\n(.*?)(?:\r?\n(?:DESCRIPTION|\r?\nComponent Kind|\*|\]))', t, re.S)
    # nets
    nets = re.findall(r'\(\r?\n([^(\r\n]+)\r?\n(.*?)\r?\n\)', t, re.S)
    refs = [c[0] for c in comps]
    ledish = [r for r in refs if re.search(r'LED', r, re.I) or 'LED' in str(comps[refs.index(r)])]
    print(f'{fn:24s} comps={len(comps):5d} nets={len(nets):5d} LED-ish={ledish[:6]}')
    print(f'   sample refs: {refs[:8]}')
    print(f'   sample nets: {[n[0].strip() for n in nets[:6]]}')
