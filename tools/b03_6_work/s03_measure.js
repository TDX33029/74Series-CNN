const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const out = {};
// 1. board outline absolute bbox
const polys = await eda.pcb_PrimitivePolyline.getAll();
out.outlines = [];
for (const p of polys) {
  let bb = null;
  try { bb = eda.pcb_Primitive.getPrimitivesBBox([p]); } catch(e) { bb = {err: String(e)}; }
  out.outlines.push({id: p.getState_PrimitiveId(), polygon: p.polygon, bbox: bb});
}
// 2. header pads
const comps = await eda.pcb_PrimitiveComponent.getAll();
const J = comps.find(c => c.getState_Designator() === 'J20206');
if (J) {
  const a = J.toAsync();
  const pins = await a.getAllPins();
  out.J_pads = pins.map(p => ({n: p.padNumber, x: p.x, y: p.y, net: p.net, pad: p.pad}));
}
// 3. all U chips pads
out.chips = {};
for (const c of comps) {
  const des = c.getState_Designator();
  if (!/^U/.test(des)) continue;
  const a = c.toAsync();
  const pins = await a.getAllPins();
  let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
  const shapes = {};
  for (const p of pins) {
    xmin = Math.min(xmin,p.x); xmax = Math.max(xmax,p.x);
    ymin = Math.min(ymin,p.y); ymax = Math.max(ymax,p.y);
    shapes[JSON.stringify(p.pad)] = (shapes[JSON.stringify(p.pad)]||0)+1;
  }
  out.chips[des] = {n: pins.length, xmin, xmax, ymin, ymax, cx: (xmin+xmax)/2, cy: (ymin+ymax)/2, rot: c.getState_Rotation(), layer: c.getState_Layer(), shapes};
}
return JSON.stringify(out);
