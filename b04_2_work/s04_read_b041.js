const B041 = '57b3a17d097a9dc8';
await eda.dmt_EditorControl.openDocument(B041);
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== B041) return 'ABORT: wrong doc ' + (doc && doc.uuid);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const des = c.getState_Designator();
  let pads = [];
  try { pads = await c.toAsync().getAllPins(); } catch(e) {}
  const xs = pads.map(p=>p.x), ys = pads.map(p=>p.y);
  out.push({des: des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer(),
    pxmin: xs.length?Math.min(...xs):null, pxmax: xs.length?Math.max(...xs):null,
    pymin: ys.length?Math.min(...ys):null, pymax: ys.length?Math.max(...ys):null});
}
const polys = await eda.pcb_PrimitivePolyline.getAll();
let outline = null;
for (const pl of polys) { try { if (pl.getState_Layer() === 11) outline = pl.polygon; } catch(e){} }
return JSON.stringify({outline: outline, comps: out});
