"""Rebind every +5V/+VLED-labelled wire on both B04-6 pages (fixes the stale
net-identity binding left by the LED incident), save, then export and verify.
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = "http://localhost:49620"
PAGES = {"s07_conv1": "fe550102fbf0e747", "b04_conn": "e6d74d8df72e476f"}


def ex(code, timeout=600):
    req = urllib.request.Request(
        BRIDGE + "/execute",
        data=json.dumps({"code": code}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout)).get("result")


def main():
    total = 0
    for page, uuid in PAGES.items():
        r = ex(f"""
const tabId = await eda.dmt_EditorControl.openDocument("{uuid}");
await new Promise(r => setTimeout(r, 1200));
const all = await eda.sch_PrimitiveWire.getAll();
const targets = all.filter(w => ["+5V", "+VLED"].includes(String(w.net)));
return {{count: targets.length, ids: targets.map(w => [w.primitiveId, String(w.net)])}};
""")
        ids = r["ids"]
        print(f"{page}: 待重绑 {len(ids)} 根")
        done = 0
        for wid, net in ids:
            rr = ex(f'''
const w = await eda.sch_PrimitiveWire.get("{wid}");
const aw = w.toAsync();
await aw.setState_Net({json.dumps(net)});
await aw.done();
return {{ok: true}};
''')
            done += 1 if rr and rr.get("ok") else 0
        print(f"  已重绑 {done}/{len(ids)}")
        total += done

    # 删除实验用的探针 +5V 标志
    r = ex('''
const tabId = await eda.dmt_EditorControl.openDocument("fe550102fbf0e747");
await new Promise(r => setTimeout(r, 1200));
try { await eda.sch_PrimitiveComponent.delete(["95be9464fe65827a"]); } catch(e) {}
return {ok: true};
''')
    # 保存两页
    for page, uuid in PAGES.items():
        ex(f'''
await eda.dmt_EditorControl.openDocument("{uuid}");
await new Promise(r => setTimeout(r, 1000));
await eda.sch_Document.save();
await new Promise(r => setTimeout(r, 1500));
''')
    print(f"共重绑 {total} 根, 已保存")

    # 最终导出验证
    r = ex('''
const tabId = await eda.dmt_EditorControl.openDocument("fe550102fbf0e747");
await new Promise(r => setTimeout(r, 1200));
const file = await eda.sch_ManufactureData.getNetlistFile("final_check", "Protel2");
const text = await file.text();
return {text};
''')
    t = r["text"]
    open(os.path.join(HERE, "boards", "B04-6_CONV1_final.txt"), "w",
         encoding="utf-8", newline="").write(t)
    lines = t.replace("\r\n", "\n").split("\n")
    cur = None
    blocks = {}
    j2p = {}
    for ln in lines:
        s = ln.strip()
        if s == "(":
            cur = None
        elif s == ")":
            cur = None
        elif cur is None and s:
            cur = s.rstrip()
            blocks[cur] = 0
        elif cur is not None and s:
            blocks[cur] += 1
            p = s.split()[0]
            if p.startswith("J20306-"):
                j2p.setdefault(int(p.split("-")[1]), []).append(cur.rstrip())
    print("导出网络数:", len(blocks))
    for n in ("+5V", "+VLED", "GND"):
        print(f"  {n}块: {blocks.get(n)}")
    for k in (5, 6, 7, 8, 9, 10):
        print(f"  J20306 pin{k}: {j2p.get(k)}")


if __name__ == "__main__":
    main()
