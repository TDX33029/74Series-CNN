#!/usr/bin/env python3
"""Import one KiCad sheet into 74CNN, assign footprints, bulk-add labels and
exclude non-parts via setDocumentSource, then verify.

Usage:
  python -I sync_new_sheet.py <Sxx.kicad_sch> <expect_parts> <expect_netports> <expect_netflags> <expect_texts>
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kicad_to_jlc import labels as extract_labels  # noqa: E402
from jlc_batch import footprint_code  # noqa: E402

BRIDGE = "http://127.0.0.1:49620/execute"
PROJECT = "6b7464fb399341afac3f4452db9da3df"
WORK = "D:/tmp/jlc_sync"


def post(code, timeout=240):
    data = json.dumps({"code": code}).encode("utf-8")
    req = urllib.request.Request(BRIDGE, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def boards():
    return post("const b=await eda.dmt_Board.getAllBoardsInfo();"
                "return b.map(x=>({name:x.name,uuid:x.uuid,pages:(x.schematic&&x.schematic.page||[]).map(p=>({name:p.name,uuid:p.uuid}))}));")


def main():
    src, ep, enp, enf, et = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    base = os.path.basename(src)
    tag = base.split("_")[0].lower()
    os.makedirs(WORK, exist_ok=True)

    before = {b["uuid"] for b in boards()["result"]}
    print("before boards", len(before), flush=True)

    # import
    raw = open(src, "rb").read()
    import base64
    b64 = base64.b64encode(raw).decode()
    code = ('const b64="' + b64 + '";\n'
            'const bin=atob(b64);const bytes=new Uint8Array(bin.length);'
            'for(let i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);\n'
            'const f=new File([bytes],"' + base + '",{type:"application/octet-stream"});\n'
            'return await eda.sys_FileManager.importProjectByProjectFile(f,"KiCad",'
            '{importOption:"ImportDocument"},{operation:"Existing Project",'
            'existingProjectUuid:"' + PROJECT + '"});')
    print("importing", base, len(raw), "bytes", flush=True)
    post(code, 300)
    time.sleep(4)

    new = None
    for _ in range(10):
        bs = boards()["result"]
        for b in bs:
            if b["uuid"] not in before and b.get("pages"):
                new = b
                break
        if new:
            break
        time.sleep(2)
    if not new:
        print("ERROR no new board", flush=True)
        return 2
    page = new["pages"][0]["uuid"]
    print("new board", new["name"], new["uuid"], "page", page, flush=True)

    # activate
    r = post('const t=await eda.dmt_EditorControl.openDocument("%s");'
             'const a=await eda.dmt_EditorControl.activateDocument(t);'
             'await new Promise(r=>setTimeout(r,2000));'
             'return {a,d:await eda.dmt_SelectControl.getCurrentDocumentInfo()};' % page)
    if (r.get("result") or {}).get("d", {}).get("uuid") != page:
        print("ERROR activate", r, flush=True)
        return 3

    # footprints
    for i in range(12):
        res = post(footprint_code(40)).get("result") or {}
        print("fp", i + 1, res, flush=True)
        if int(res.get("remaining", 0)) == 0:
            break
    post("await eda.sch_Document.save();return true;")

    # document source
    r = post("const s=await eda.sys_FileManager.getDocumentSource();return s;")
    s = r.get("result")
    if not isinstance(s, str) or len(s) < 1000:
        print("ERROR source", r, flush=True)
        return 4
    src_path = os.path.join(WORK, "%s_source.txt" % tag)
    open(src_path, "w", encoding="utf-8").write(s)

    # labels json
    items = extract_labels(open(src, encoding="utf-8").read())
    lab_path = os.path.join(WORK, "%s_labels.json" % tag)
    json.dump(items, open(lab_path, "w", encoding="utf-8"), ensure_ascii=False)
    print("labels", len(items), flush=True)

    # bulk transform
    mod_path = os.path.join(WORK, "%s_source_mod.txt" % tag)
    subprocess.run([sys.executable, "-I", "D:/tmp/jlc_sync/bulk_texts_flags.py",
                    src_path, lab_path, mod_path], check=True)
    mod = open(mod_path, encoding="utf-8").read()
    print("modified source", len(mod), flush=True)

    # set source
    code = ('const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();'
            'if(d.uuid!=="%s")return {err:"wrong doc",d};'
            'const src=%s;const r=await eda.sys_FileManager.setDocumentSource(src);'
            'return {r};' % (page, json.dumps(mod)))
    r = post(code, 300)
    print("setSource", r.get("success"), (r.get("result") or {}), flush=True)

    # reload + verify
    post('const t=await eda.dmt_EditorControl.openDocument("%s");'
         'await eda.dmt_EditorControl.activateDocument(t);'
         'await new Promise(r=>setTimeout(r,2500));return true;' % page)
    code = ('const c=await eda.sch_PrimitiveComponent.getAll();const t=await eda.sch_PrimitiveText.getAll();'
            'const w=await eda.sch_PrimitiveWire.getAll();const cnt={};'
            'for(const x of c){cnt[x.componentType]=(cnt[x.componentType]||0)+1;}'
            'const parts=c.filter(x=>x.componentType==="part");'
            'const al={};for(const x of t){al[String(x.alignMode)]=(al[String(x.alignMode)]||0)+1;}'
            'return {cnt,texts:t.length,wires:w.length,'
            'noFp:parts.filter(p=>!p.footprint||!p.footprint.name).length,'
            'badNon:c.filter(x=>x.componentType!=="part"&&(x.addIntoBom||x.addIntoPcb)).length,align:al};')
    v = post(code).get("result") or {}
    print("VERIFY", json.dumps(v, ensure_ascii=False), flush=True)
    cnt = v.get("cnt", {})
    ok = (cnt.get("part") == ep and cnt.get("netport") == enp and int(cnt.get("netflag", 0)) == enf
          and v.get("texts") == et and v.get("noFp") == 0 and v.get("badNon") == 0)
    post("await eda.sch_Document.save();return true;")
    print("RESULT", "PASS" if ok else "FAIL", new["name"], new["uuid"], page, flush=True)
    return 0 if ok else 5


if __name__ == "__main__":
    sys.exit(main())
