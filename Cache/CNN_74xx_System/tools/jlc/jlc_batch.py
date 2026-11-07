#!/usr/bin/env python3
"""Generate EasyEDA /execute request JSON files for repetitive schematic work.

Usage:
  python -I jlc_batch.py activate <page_uuid> <outdir>
  python -I jlc_batch.py labels <labels.json> <page_uuid> <outdir> [batch]
  python -I jlc_batch.py footprints <outdir> [batch]
  python -I jlc_batch.py exclude <outdir> [batch] <page_uuid>
  python -I jlc_batch.py verify <outdir>

The generated files are POSTed one at a time to the bridge /execute endpoint.
Footprint assignment is idempotent: it always processes the first N parts that
still have no footprint name, so a timed-out request can be retried safely.
"""
import json
import os
import sys

FP_MAP = {
    "Conn_02x20": ("28846765b72b82e7", "HDR-TH_40P-P2.54-V-R2-C20-S2.54-1"),
    "Conn_02x16": ("aba78d165edefae4", "CONN-TH_32P-P2.54_C9900010108"),
    "Conn_02x12": ("255c0e5285ea710d", "HDR-TH_24P-P2.54-V-M-R2-C12-S2.54-2"),
    "Conn_02x10": ("1e33bd087f44856a", "HDR-TH_20P-P2.54-V-M-R2-C10-S2.54"),
    "Conn_02x02": ("07c1f5b6a34479c1", "HDR-TH_4P-P2.54-V-F-R2-C2-S2.54"),
    "Conn_01x02": ("97a28fdcd7a0e05b", "HDR-SMD_2P-P2.54-V-F-LS4.9"),
    "Conn_01x03": ("654bb2be0d497120", "HDR-TH_PM2.54-1X3PZZ-H8.5"),
    "DIP14": ("5fbc27e5b47b1d75", "PDIP-14"),
    "DIP16": ("cbab301e5fcc9cfe", "PDIP-16"),
    "DIP20": ("96709c1c96c0dc46", "PDIP-20"),
    "DIP28": ("5e745cbf9aa52a38", "PDIP-28"),
    "CAP": ("a6acf80ecb70dfc9", "CAP-TH"),
    "RES": ("b080637a828494eb", "RES-TH"),
    "TP": ("be47545c61f5a966", "TESTPOINT-TH"),
    "LED": ("b5b6ab5625dae23f", "LED-TH"),
    "R_NET": ("51b71e540536fb08", "SIP9"),
    "OSC": ("1bf2b016f2786394", "OSC-SMD-4P"),
    "SW": ("dfb55335d44b6e80", "SW-SMD"),
}


def write_req(path, code):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"code": code}, f, ensure_ascii=False)


def activate(page_uuid, outdir):
    os.makedirs(outdir, exist_ok=True)
    code = '''const tabId=await eda.dmt_EditorControl.openDocument("%s");
await eda.dmt_EditorControl.activateDocument(tabId);
await new Promise(r=>setTimeout(r,800));
return await eda.dmt_SelectControl.getCurrentDocumentInfo();''' % page_uuid
    write_req(os.path.join(outdir, "activate.json"), code)
    print("activate request written")


def labels(labels_json, page_uuid, outdir, batch):
    items = json.load(open(labels_json, encoding="utf-8"))
    os.makedirs(outdir, exist_ok=True)
    n = 0
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]
        code = '''const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(d.uuid!=="%s")return {err:"wrong document",doc:d,ok:0,skip:0};
const items=%s;
const ex=(await eda.sch_PrimitiveText.getAll()).map(t=>String(t.content)+"|"+Math.round(t.x)+"|"+Math.round(t.y));
let ok=0,skip=0;
for(const it of items){
 const x=it[0]+(it[3]===90?3:0), y=it[1]+(it[3]===90?0:3);
 const key=it[2]+"|"+Math.round(x)+"|"+Math.round(y);
 if(ex.includes(key)){skip++;continue;}
 const r=await eda.sch_PrimitiveText.create(x,y,it[2],it[3],null,null,5.90551,false,false,false,it[4]);
 if(r)ok++;
}
return {ok,skip,total:(await eda.sch_PrimitiveText.getAll()).length};''' % (page_uuid, json.dumps(chunk, ensure_ascii=False))
        write_req(os.path.join(outdir, "text_%03d.json" % n), code)
        n += 1
    print("labels=%d batches=%d batch_size=%d" % (len(items), n, batch))


def footprint_code(batch):
    m = {k: {"uuid": v[0], "name": v[1]} for k, v in FP_MAP.items()}
    return '''const M=%s;
function pick(n){
 if(n.includes("Conn_02x20"))return M.Conn_02x20;
 if(n.includes("Conn_02x16"))return M.Conn_02x16;
 if(n.includes("Conn_02x12"))return M.Conn_02x12;
 if(n.includes("Conn_02x10"))return M.Conn_02x10;
 if(n.includes("Conn_02x02"))return M.Conn_02x02;
 if(n.includes("Conn_01x02"))return M.Conn_01x02;
 if(n.includes("Conn_01x03"))return M.Conn_01x03;
 if(n.includes("27C512")||n.includes("28C256")||n.includes("HY6264"))return M.DIP28;
 if(n.includes("R_Network08"))return M.R_NET;
 if(n.includes("74HC00")||n.includes("74HC02")||n.includes("74HC04")||n.includes("74HC08")||n.includes("74HC32")||n.endsWith("74HC74"))return M.DIP14;
 if(n.includes("74HC157")||n.includes("74HC161")||n.includes("74HC138")||n.includes("74HC238")||n.includes("74HC283")||n.includes("74HC85")||n.includes("74LS148"))return M.DIP16;
 if(n.includes("74HCT273")||n.includes("74HCT574")||n.includes("74HCT541")||n.includes("74HCT245")||n.includes("74HC245")||n.includes("74HC688"))return M.DIP20;
 if(n.includes("TestPoint"))return M.TP;
 if(n.includes("Device_C"))return M.CAP;
 if(n.includes("Device_R"))return M.RES;
 if(n.includes("Device_LED"))return M.LED;
 if(n.includes("ASE"))return M.OSC;
 if(n.includes("SW_Push"))return M.SW;
 return null;
}
const parts=(await eda.sch_PrimitiveComponent.getAll()).filter(x=>x.componentType==="part"&&(!x.footprint||!x.footprint.name));
const batch=parts.slice(0,%d);let ok=0;const skip={};
for(const c of batch){const fp=pick(c.name||"");if(!fp){skip[c.name]=(skip[c.name]||0)+1;continue;}
 const props=Object.assign({},c.otherProperty||{},{Footprint:fp.uuid});
 await eda.sch_PrimitiveComponent.modify(c.primitiveId,{otherProperty:props});ok++;}
return {ok,remaining:parts.length-ok,skip};''' % (json.dumps(m, ensure_ascii=False), batch)


def footprints(outdir, batch):
    os.makedirs(outdir, exist_ok=True)
    write_req(os.path.join(outdir, "fp.json"), footprint_code(batch))
    print("footprint request written, batch=%d" % batch)


def exclude_code(batch, page_uuid):
    return '''const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(d.uuid!=="%s")return {err:"wrong document",doc:d,ok:0,remaining:-1};
const all=(await eda.sch_PrimitiveComponent.getAll()).filter(x=>x.componentType!=="part"&&(x.addIntoBom||x.addIntoPcb));
const batch=all.slice(0,%d);let ok=0;
for(const c of batch){const a=c.toAsync();a.setState_AddIntoBom(false);a.setState_AddIntoPcb(false);await a.done();ok++;}
return {ok,remaining:all.length-batch.length};''' % (page_uuid, batch)


def exclude(outdir, batch, page_uuid):
    os.makedirs(outdir, exist_ok=True)
    write_req(os.path.join(outdir, "exclude.json"), exclude_code(batch, page_uuid))
    print("exclude request written, batch=%d" % batch)


def verify(outdir):
    os.makedirs(outdir, exist_ok=True)
    code = '''const c=await eda.sch_PrimitiveComponent.getAll();
const parts=c.filter(x=>x.componentType==="part");
const cnt={};for(const x of c){cnt[x.componentType]=(cnt[x.componentType]||0)+1;}
const noFp=parts.filter(p=>!p.footprint||!p.footprint.name);
const noVal=parts.filter(p=>!p.otherProperty||!p.otherProperty.Value);
const badNon=c.filter(x=>x.componentType!=="part"&&(x.addIntoBom||x.addIntoPcb));
const t=await eda.sch_PrimitiveText.getAll();
const w=await eda.sch_PrimitiveWire.getAll();
const al={};for(const x of t){al[String(x.alignMode)]=(al[String(x.alignMode)]||0)+1;}
return {cnt,total:c.length,parts:parts.length,noFp:noFp.map(p=>p.designator),noFpCount:noFp.length,noValCount:noVal.length,badNon:badNon.length,texts:t.length,align:al,wires:w.length};'''
    write_req(os.path.join(outdir, "verify.json"), code)
    print("verify request written")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "activate":
        activate(sys.argv[2], sys.argv[3])
    elif cmd == "labels":
        labels(sys.argv[2], sys.argv[3], sys.argv[4],
               int(sys.argv[5]) if len(sys.argv) > 5 else 20)
    elif cmd == "footprints":
        footprints(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 40)
    elif cmd == "exclude":
        exclude(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 40, sys.argv[4])
    elif cmd == "verify":
        verify(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
