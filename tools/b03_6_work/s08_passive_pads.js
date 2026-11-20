const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = {};
for (const c of comps) {
  const des = c.getState_Designator();
  if (!/^(R|Q|LED|RP|C)/.test(des)) continue;
  const a = c.toAsync();
  const pins = await a.getAllPins();
  let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
  const pl = [];
  for (const p of pins) {
    xmin = Math.min(xmin,p.x); xmax = Math.max(xmax,p.x);
    ymin = Math.min(ymin,p.y); ymax = Math.max(ymax,p.y);
    pl.push({n: p.padNumber, dx: +(p.x - c.getState_X()).toFixed(1), dy: +(p.y - c.getState_Y()).toFixed(1), net: p.net, pad: p.pad});
  }
  out[des] = {n: pins.length, halfx: +((xmax-xmin)/2).toFixed(1), halfy: +((ymax-ymin)/2).toFixed(1), rot: c.getState_Rotation(), layer: c.getState_Layer(), pins: pl};
}
return JSON.stringify(out);
