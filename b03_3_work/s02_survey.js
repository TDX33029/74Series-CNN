const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;

// 1. board outline
const polys = await eda.pcb_PrimitivePolyline.getAll();
const outlines = polys.map(p => ({id: p.getState_PrimitiveId ? p.getState_PrimitiveId() : '?', polygon: p.polygon, layer: p.getState_Layer ? p.getState_Layer() : '?'}));

// 2. all components
const comps = await eda.pcb_PrimitiveComponent.getAll();
const cl = comps.map(c => ({
  des: c.getState_Designator(),
  x: c.getState_X(), y: c.getState_Y(),
  rot: c.getState_Rotation(),
  layer: c.getState_Layer(),
  name: c.getState_Name()
}));

// 3. all pads bbox
const pads = await eda.pcb_PrimitivePad.getAll();
let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
for (const p of pads) {
  if (p.x < xmin) xmin = p.x; if (p.x > xmax) xmax = p.x;
  if (p.y < ymin) ymin = p.y; if (p.y > ymax) ymax = p.y;
}
return JSON.stringify({nOutlines: outlines.length, outlines, nComps: cl.length, comps: cl, padBBox: {xmin, xmax, ymin, ymax}, nPads: pads.length});
