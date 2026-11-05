#!/usr/bin/env python3
"""KiCad -> 嘉立创EDA 转换辅助脚本（本地执行，不依赖 EDA 运行时）。

用法:
  python -I kicad_to_jlc.py labels  <input.kicad_sch> <out_labels.json>
  python -I kicad_to_jlc.py importreq <input.kicad_sch> <project_uuid> <out_req.json>
  python -I kicad_to_jlc.py inventory <input.kicad_sch>

说明:
  labels    : 抽取 KiCad 本地标签 (label ...)，输出 [[X,Y,NAME,ROT,ALIGN], ...]
              X = x_mm / 0.254, Y = -y_mm / 0.254；文本创建时再 +3 单位偏移。
  importreq : 生成 POST /execute 的 JSON，把 .kicad_sch 以 base64 File 形式导入已有工程。
  inventory : 打印 lib_id 统计，便于确认封装映射。
"""
import base64
import json
import re
import sys


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def labels(src):
    pat = re.compile(
        r'\(label "([^"]+)"\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)(.*?)\n\t\)',
        re.S,
    )
    items = []
    for m in pat.finditer(src):
        name, x, y, rot, body = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)), m.group(5)
        just = re.search(r"\(justify ([^)]*)\)", body)
        justify = just.group(1) if just else ""
        X = round(x / 0.254, 4)
        Y = round(-y / 0.254, 4)
        rotation = 90 if rot in (90.0, 270.0) else 0
        if rotation == 90:
            align = 2 if "left" in justify else 8
        else:
            align = 8 if "right" in justify else 2
        items.append([X, Y, name, rotation, align])
    return items


def import_request(path, project_uuid, out_path):
    raw = open(path, "rb").read()
    b64 = base64.b64encode(raw).decode()
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    code = (
        'const b64="' + b64 + '";\n'
        "const bin=atob(b64); const bytes=new Uint8Array(bin.length); "
        "for(let i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);\n"
        'const file=new File([bytes],"' + name + '",{type:"application/octet-stream"});\n'
        'const p=await eda.sys_FileManager.importProjectByProjectFile(file,"KiCad",'
        '{importOption:"ImportDocument"},{operation:"Existing Project",'
        'existingProjectUuid:"' + project_uuid + '"});\n'
        "return p;"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"code": code}, f)
    print(f"wrote {out_path} ({len(code)} chars, {len(raw)} bytes source)")


def inventory(src):
    libs = re.findall(r'\(lib_id "([^"]+)"', src)
    counts = {}
    for lib in libs:
        counts[lib] = counts.get(lib, 0) + 1
    print(f"symbols={len(libs)} unique={len(counts)}")
    for k in sorted(counts, key=lambda x: (-counts[x], x)):
        print(f"{counts[k]:5d}  {k}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "labels":
        src = read(sys.argv[2])
        items = labels(src)
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        print(f"labels={len(items)} -> {sys.argv[3]}")
    elif cmd == "importreq":
        import_request(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "inventory":
        inventory(read(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
