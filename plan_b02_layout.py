import json

# Band plan: chips live in y[12,1200] (above LED row at y1214). 11 chips, 6 columns.
# Column x centers chosen to avoid: Q/LED block x[1290,1369] at y[1505,1580] (no conflict, band ends 1200)
# and right-side LEDs x[2716,3750] y[1543,1812] (no conflict, band ends 1200).
# Only true constraint in band: chips vs chips >=80; left edge >=12; top edge >=12.
# Vertical space per column: 1200-24 = 1176 for (sum hy) + 80*(n-1).
CHIPS = {}
# hy = y extent after rot=90 = rot0 h (pin column span = chip length): U2001 614.2? No:
# rot0 h for U2001 = 614.2 = pin column span (28 pins, 22.54 pitch) => chip length.
# After rot=90 chip length lies along y => y extent = rot0 h. Correct mapping: hy = rot0 h.
# U2001 hy=614.2, PDIP-20 hy~300-312, DIP-14/16 hy~290-330.

GAP, EDGE, BAND_BOTTOM = 80.0, 12.0, 1200.0
# Column plan (2 chips each, ordered by signal flow; U2001 column single):
# c0: U2005 + U2009   (IO near connector)      sum=600 +80 = 680 <=1176 OK
# c1: U2003 + U2011   (control -> ROM; U2011<->U2009) 642.6+80=722 OK
# c2: U2001 + U2007   (ROM + gate) 614.2+289.8+80=984 OK
# c3: U2004 + U2008   (ROM output + out stage) 300+311+80=691 OK
# c4: U2002 + U2006   (latch bank) 300+312.6+80=692 OK
# c5: U2010           (reset glue) 330 OK
COLS = [["U2005","U2009"],["U2003","U2011"],["U2001","U2007"],["U2004","U2008"],["U2002","U2006"],["U2010"]]
X0 = 120.0   # column 0 left pad edge (start a bit inside; connector is outside board at y<0)

halves_x = {  # hx (x extent after rot=90) = rot0 h (pin column span = chip length)
    "U2001": 614.2, "U2002": 300.0, "U2003": 312.6, "U2004": 300.0, "U2005": 300.0,
    "U2006": 312.6, "U2007": 289.8, "U2008": 311.0, "U2009": 300.0, "U2010": 330.7, "U2011": 330.7,
}
hy_x = {  # hy (y extent after rot=90) = rot0 w (pin row span = chip width)
    "U2001": 650.0, "U2002": 450.0, "U2003": 450.0, "U2004": 350.0, "U2005": 450.0,
    "U2006": 350.0, "U2007": 350.0, "U2008": 450.0, "U2009": 300.0, "U2010": 300.0, "U2011": 300.0,
}

xs = []
x_edge = X0
for col in COLS:
    hw = max(halves_x[d] for d in col)
    cx = x_edge + hw
    xs.append(cx)
    x_edge = cx + hw + GAP
last_right = xs[-1] + halves_x["U2010"]
led_zone = 3937.0 - last_right

placements = {}
ok = True
for i, col in enumerate(COLS):
    cx = xs[i]
    y_edge = EDGE
    for d in col:
        hy = hy_x[d]
        cy = y_edge + hy
        placements[d] = (cx, cy)
        y_edge = cy + hy + GAP
    if y_edge - GAP > BAND_BOTTOM + 1e-6:
        ok = False; print(f"COL {i} bottom {y_edge-GAP:.0f} > {BAND_BOTTOM}")
    if xs[i] - halves_x[col[0]] < 12 - 1e-6:
        ok = False; print(f"COL {i} left edge fail")
    if xs[i] + halves_x[col[-1]] > 3937 - 12:
        ok = False; print(f"COL {i} right edge fail")

# pairwise overlap check (all chips, pad bbox with 6mil min edge gap requirement)
boxes = {}
for d,(cx,cy) in placements.items():
    hx, hy = halves_x[d], hy_x[d]
    boxes[d] = (cx-hx, cx+hx, cy-hy, cy+hy)
ds = list(CHIPS)
for i in range(len(ds)):
    for j in range(i+1, len(ds)):
        a, b = ds[i], ds[j]
        A, B = boxes[a], boxes[b]
        if not (A[1]+6 <= B[0] or B[1]+6 <= A[0] or A[3]+6 <= B[2] or B[3]+6 <= A[2]):
            # only fail if BOTH x and y ranges overlap by >6 pad-edge gap
            xo = min(A[1],B[1]) - max(A[0],B[0])
            yo = min(A[3],B[3]) - max(A[2],B[2])
            if xo > 6 and yo > 6:
                ok = False; print("CHIP OVERLAP", a, b, xo, yo)

print("x centers:", [round(c,1) for c in xs], "last right:", round(last_right,1), "LED zone:", round(led_zone,1))
print("ALL OK" if ok else "FAILURES ABOVE")
print()
order = []
for col in COLS:
    for d in col:
        cx, cy = placements[d]
        order.append([d, round(cx,1), round(cy,1)])
        b = boxes[d]
        print(f"{d}: x={cx:.0f} y={cy:.0f} pads x[{b[0]:.0f},{b[1]:.0f}] y[{b[2]:.0f},{b[3]:.0f}]")
with open(r"D:\Document\tempPrj\74Series-CNN\B02_TIMING_placement_plan.json","w") as f:
    json.dump({"rot":90, "placements":order, "led_zone_start":round(last_right,1), "led_zone_width":round(led_zone,1)}, f, indent=1)
