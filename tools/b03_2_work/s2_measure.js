const TARGET = '7f08bbdec72478d8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT:' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const byDes = {};
for (const c of comps) byDes[c.getState_Designator()] = c;
const caps = comps.filter(c => /^C/i.test(c.getState_Designator())).map(c => c.getState_Designator());
// outline absolute bbox + object offset
const polys = await eda.pcb_PrimitivePolyline.getAll();
const pl = polys[0];
let plX = null, plY = null;
try { plX = pl.getState_X(); plY = pl.getState_Y(); } catch (e) {}
let plBBox = null;
try { const b = eda.pcb_Primitive.getPrimitivesBBox([pl]); plBBox = {minX: b.minX, maxX: b.maxX, minY: b.minY, maxY: b.maxY}; } catch (e) { plBBox = 'ERR:' + e; }
async function padsOf(c) { const a = c.toAsync(); const ps = await a.getAllPins(); return ps || []; }
const J = byDes['J20202'];
const jp = (await padsOf(J)).map(p => ({n: p.padNumber, x: Math.round(p.x * 100) / 100, y: Math.round(p.y * 100) / 100, net: p.net, pad: p.pad}));
const chips = ['U4009','U4010','U4011','U4014','U4016','U4017','U4018','U4031','U4049'];
const chipInfo = {};
for (const des of chips) {
  const ps = await padsOf(byDes[des]);
  let xmin = 1e9, xmax = -1e9, ymin = 1e9, ymax = -1e9; const shapes = {};
  for (const p of ps) { xmin = Math.min(xmin, p.x); xmax = Math.max(xmax, p.x); ymin = Math.min(ymin, p.y); ymax = Math.max(ymax, p.y); const k = JSON.stringify(p.pad); shapes[k] = (shapes[k] || 0) + 1; }
  chipInfo[des] = {n: ps.length, xmin: Math.round(xmin*100)/100, xmax: Math.round(xmax*100)/100, ymin: Math.round(ymin*100)/100, ymax: Math.round(ymax*100)/100, shapes: shapes};
}
const samp = ['LED_LOAD_DATA0','LEDP1','LED_MEM_D0','Q3009','Q3011','R3017','R3018','R1','RP1'];
const sampInfo = {};
for (const des of samp) {
  const ps = await padsOf(byDes[des]);
  sampInfo[des] = ps.map(p => ({n: p.padNumber, x: Math.round(p.x*100)/100, y: Math.round(p.y*100)/100, net: p.net, pad: p.pad}));
}
const passives = comps.filter(c => { const d = c.getState_Designator(); return /^(LED|Q|R\d|RP)/.test(d); });
const netMap = {};
for (const c of passives) { const ps = await padsOf(c); netMap[c.getState_Designator()] = ps.map(p => p.net); }
const drc = await eda.pcb_Drc.check(true, false, true);
const drcArr = Array.isArray(drc) ? drc.map(c => ({name: c.name, n: (c.list || []).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)})) : 'no-array:' + JSON.stringify(drc).slice(0, 200);
return JSON.stringify({caps: caps, pl: {x: plX, y: plY, polygon: pl.polygon && pl.polygon.polygon, bbox: plBBox}, jpads: jp, chipInfo: chipInfo, sampInfo: sampInfo, netMap: netMap, drc: drcArr});
