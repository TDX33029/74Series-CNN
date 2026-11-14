import os

path = r"D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/top_20261112c.net"
depth = 0
instr = False
esc = False
with open(path, encoding="utf-8") as f:
    for ln, line in enumerate(f, 1):
        for ch in line:
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
            else:
                if ch == '"':
                    instr = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth < 0:
                        print(f"NEGATIVE depth at line {ln}: {line[:150]}")
                        raise SystemExit
print("end depth:", depth, "in-string:", instr)
print("file size:", os.path.getsize(path))
