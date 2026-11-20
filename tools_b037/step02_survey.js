const TARGET = '046a237b7518687e';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const out = {};
// board outline
const polys = await eda.pcb_PrimitivePolyline.getAll();
out.polylines = polys.map(p => ({id: p.getState_PrimitiveId ? p.getState_PrimitiveId() : null, polygon: p.polygon, layer: p.getState_Layer ? p.getState_Layer() : null}));
// all pads for header + bbox
const pads = await eda.pcb_PrimitivePad.getAll();
let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
const jpads = [];
for (const p of pads) {
  xmin=Math.min(xmin,p.x); xmax=Math.max(xmax,p.x);
  ymin=Math.min(ymin,p.y); ymax=Math.max(ymax,p.y);
}
out.allPadsBBox = {xmin,xmax,ymin,ymax};
out.padCount = pads.length;
// header pads: net contains nothing special; find by primitive parent - instead collect pads whose net or designator J2
// get components
const comps = await eda.pcb_PrimitiveComponent.getAll();
out.compCount = comps.length;
out.comps = comps.map(c => ({
  des: c.getState_Designator(),
  x: c.getState_X(), y: c.getState_Y(),
  rot: c.getState_Rotation(),
  layer: c.getState_Layer()
}));
return JSON.stringify(out);
