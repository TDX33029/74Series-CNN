// step2: measure board outline, header pads, all components bbox
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;

const out = {};

// board outline
const polys = await eda.pcb_PrimitivePolyline.getAll();
out.polylines = [];
for (const pl of polys) {
  out.polylines.push({
    id: pl.getState_PrimitiveId ? pl.getState_PrimitiveId() : null,
    layer: pl.getState_Layer ? pl.getState_Layer() : null,
    polygon: pl.polygon
  });
}

// all pads (headers etc.) — overall bbox
const pads = await eda.pcb_PrimitivePad.getAll();
let pxmin=1e18,pxmax=-1e18,pymin=1e18,pymax=-1e18;
const padList = [];
for (const p of pads) {
  pxmin=Math.min(pxmin,p.x); pxmax=Math.max(pxmax,p.x);
  pymin=Math.min(pymin,p.y); pymax=Math.max(pymax,p.y);
  padList.push({x:p.x, y:p.y, net:p.net, shape:p.pad, layer:p.layer});
}
out.padBBox = {pxmin,pxmax,pymin,pymax, count: pads.length};

// components overview
const comps = await eda.pcb_PrimitiveComponent.getAll();
out.comps = [];
for (const c of comps) {
  out.comps.push({
    des: c.getState_Designator(),
    x: c.getState_X(), y: c.getState_Y(),
    rot: c.getState_Rotation(),
    layer: c.getState_Layer ? c.getState_Layer() : null,
    id: c.getState_PrimitiveId ? c.getState_PrimitiveId() : null
  });
}
return JSON.stringify(out);
