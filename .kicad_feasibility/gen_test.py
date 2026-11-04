import re, uuid, os

LIB = r"C:/Program Files/KiCad/10.0/share/kicad/symbols/74xx.kicad_sym"
OUT = "test.kicad_sch"

def extract_symbol(path, name):
    s = open(path, encoding="utf-8").read()
    key = f'(symbol "{name}"'
    i = s.find(key)
    if i < 0: raise SystemExit("not found")
    depth = 0; j = i
    while j < len(s):
        if s[j] == '(': depth += 1
        elif s[j] == ')':
            depth -= 1
            if depth == 0:
                j += 1; break
        j += 1
    return s[i:j]

def pins(block):
    # pin ... (at x y angle) ... (number "n")
    out = []
    for m in re.finditer(r'\(pin\s+(\w+)\s+\w+\s*\(at\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\d+)\)(.*?)\n\t\t\)', block, re.S):
        body = m.group(5)
        num = re.search(r'\(number\s+"([^"]+)"', body)
        nm = re.search(r'\(name\s+"([^"]+)"', body)
        if num:
            out.append((num.group(1), nm.group(1) if nm else "", float(m.group(2)), float(m.group(3)), int(m.group(4))))
    return out

block = extract_symbol(LIB, "74LS161")
block = block.replace('(symbol "74LS161"', '(symbol "74xx:74LS161"', 1)
ps = pins(block)
print("pins:", len(ps), ps[:5])

SX, SY = 100.0, 100.0
def gpos(px, py):
    return (SX + px, SY - py)

# choose first 4 pins and wire them left
wires = []
labels = []
for idx, (num, name, px, py, ang) in enumerate(ps[:4]):
    x, y = gpos(px, py)
    # pin points left (angle 0), endpoint is at x,y; wire 10mm left
    wires.append((x, y, x-10, y))
    labels.append((f"N{num}", x-10, y, 180))

def U(): return str(uuid.uuid4())

parts = []
parts.append('(kicad_sch\n\t(version 20250610)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n')
parts.append(f'\t(uuid "{U()}")\n\t(paper "A4")\n')
parts.append('\t(title_block\n\t\t(title "Feasibility Test")\n\t\t(date "2026-11-04")\n\t)\n')
parts.append('\t(lib_symbols\n')
parts.append('\t\t' + block.replace('\n', '\n\t\t') + '\n')
parts.append('\t)\n')
for (x1,y1,x2,y2) in wires:
    parts.append(f'\t(wire\n\t\t(pts\n\t\t\t(xy {x1} {y1}) (xy {x2} {y2})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "{U()}")\n\t)\n')
for (name,x,y,ang) in labels:
    just = "right" if ang == 180 else "left"
    parts.append(f'\t(global_label "{name}"\n\t\t(shape input)\n\t\t(at {x} {y} {ang})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify {just})\n\t\t)\n\t\t(uuid "{U()}")\n\t)\n')
parts.append(f'\t(symbol\n\t\t(lib_id "74xx:74LS161")\n\t\t(at {SX} {SY} 0)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "{U()}")\n')
parts.append('\t\t(property "Reference" "U1"\n\t\t\t(at 100 80 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')
parts.append('\t\t(property "Value" "74LS161"\n\t\t\t(at 100 120 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n')
parts.append('\t\t(property "Footprint" "Package_DIP:DIP-16_W7.62mm"\n\t\t\t(at 100 100 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n')
parts.append('\t\t(property "Datasheet" ""\n\t\t\t(at 100 100 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n')
for (num, nm, px, py, ang) in ps:
    parts.append(f'\t\t(pin "{num}"\n\t\t\t(uuid "{U()}")\n\t\t)\n')
parts.append('\t\t(instances\n\t\t\t(project "test"\n\t\t\t\t(path "/ROOTUUID"\n\t\t\t\t\t(reference "U1")\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n')
parts.append('\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n')
txt = ''.join(parts)
root_uuid = re.search(r'\(uuid "([^"]+)"\)', txt).group(1)
txt = txt.replace('ROOTUUID', root_uuid)
open(OUT, "w", encoding="utf-8").write(txt)
print("wrote", OUT, os.path.getsize(OUT))
