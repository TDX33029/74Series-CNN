const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const des = c.getState_Designator();
  let pads = null;
  try {
    const a = c.toAsync();
    pads = await a.getAllPins();
  } catch(e) { pads = null; }
  if (!pads || pads.length === 0) {
    try {
      pads = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId ? c.getState_PrimitiveId() : undefined);
    } catch(e) {}
  }
  const pl = [];
  if (pads && pads.length) {
    for (const p of pads) {
      pl.push({n: p.padNumber, x: p.x, y: p.y, net: p.net, pad: p.pad, hole: p.holeDiameter});
    }
  }
  out.push({des: des, npads: pl.length, pads: pl});
}
return JSON.stringify(out);
