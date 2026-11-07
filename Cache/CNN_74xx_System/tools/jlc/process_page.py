#!/usr/bin/env python3
"""Process an already-imported page: footprints, bulk labels+flags, verify.

Usage:
  python -I process_page.py <page_uuid> <source.kicad_sch> <expect_parts> <expect_netports> <expect_netflags> <expect_texts>
"""
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kicad_to_jlc import labels as extract_labels  # noqa: E402
from jlc_batch import footprint_code  # noqa: E402

BRIDGE = "http://127.0.0.1:49620/execute"
WORK = "D:/tmp/jlc_sync"


def post(code, timeout=300):
    data = json.dumps({"code": code}).encode("utf-8")
    req = urllib.request.Request(BRIDGE, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    page, src = sys.argv[1], sys.argv[2]
    ep, enp, enf, et = map(int, sys.argv[3:7])
    tag = os.path.basename(src).split("_")[0].lower()

    r = post('const t=await eda.dmt_EditorControl.openDocument("%s");'
             'const a=await eda.dmt_EditorControl.activateDocument(t);'
             'await new Promise(r=>setTimeout(r,2500));'
             'return {a,d:await eda.dmt_SelectControl.getCurrentDocumentInfo()};' % page)
    d = (r.get("result") or {}).get("d", {})
    print("activate", d.get("uuid"), flush=True)
    if d.get("uuid") != page:
        print("ERROR activate", r, flush=True)
        return 3

    for i in range(15):
        res = post(footprint_code(40)).get("result") or {}
        print("fp", i + 1, res, flush=True)
        if int(res.get("remaining", 0)) == 0:
            break
    post("await eda.sch_Document.save();return true;")

    r = post("const s=await eda.sys_FileManager.getDocumentSource();return s;")
    s = r.get("result")
    if not isinstance(s, str) or len(s) < 1000:
        print("ERROR source", r, flush=True)
        return 4
    src_path = os.path.join(WORK, "%s_source.txt" % tag)
    open(src_path, "w", encoding="utf-8").write(s)

    items = [] if (len(sys.argv) > 7 and sys.argv[7] == "nolabels") else extract_labels(open(src, encoding="utf-8").read())
    lab_path = os.path.join(WORK, "%s_labels.json" % tag)
    json.dump(items, open(lab_path, "w", encoding="utf-8"), ensure_ascii=False)
    print("labels", len(items), flush=True)

    mod_path = os.path.join(WORK, "%s_source_mod.txt" % tag)
    subprocess.run([sys.executable, "-I", "D:/tmp/jlc_sync/bulk_texts_flags.py",
                    src_path, lab_path, mod_path], check=True)
    mod = open(mod_path, encoding="utf-8").read()
    print("modified source", len(mod), flush=True)

    code = ('const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();'
            'if(d.uuid!=="%s")return {err:"wrong doc",d};'
            'const src=%s;const r=await eda.sys_FileManager.setDocumentSource(src);'
            'return {r};' % (page, json.dumps(mod)))
    r = post(code, 400)
    print("setSource", r.get("success"), (r.get("result") or {}), flush=True)

    post('const t=await eda.dmt_EditorControl.openDocument("%s");'
         'await eda.dmt_EditorControl.activateDocument(t);'
         'await new Promise(r=>setTimeout(r,3000));return true;' % page)
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
    print("RESULT", "PASS" if ok else "FAIL", page, flush=True)
    return 0 if ok else 5


if __name__ == "__main__":
    sys.exit(main())
