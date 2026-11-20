const TARGET = '1595c28f09776867';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + (doc && doc.uuid);
const polys = await eda.pcb_PrimitivePolyline.getAll();
let outline = null;
const outlines = [];
for (const pl of polys) {
  try {
    const layer = pl.getState_Layer ? pl.getState_Layer() : null;
    const pg = pl.polygon;
    outlines.push({layer: layer, polygon: pg});
    if (layer === 11) outline = pg;
  } catch (e) { outlines.push({err: String(e)}); }
}
const comps = await eda.pcb_PrimitiveComponent.getAll();
const list = [];
for (const c of comps) {
  list.push({des: c.getState_Designator(), x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer ? c.getState_Layer() : null, name: c.getState_Name()});
}
const pads = await eda.pcb_PrimitivePad.getAll();
let padCount = pads.length;
let pxmin=1e9,pxmax=-1e9,pymin=1e9,pymax=-1e9;
for (const p of pads) { pxmin=Math.min(pxmin,p.x); pxmax=Math.max(pxmax,p.x); pymin=Math.min(pymin,p.y); pymax=Math.max(pymax,p.y); }
return JSON.stringify({outline: outline, allOutlines: outlines.slice(0,10), compCount: comps.length, padCount: padCount, padBBox: {xmin:pxmin,xmax:pxmax,ymin:pymin,ymax:pymax}, comps: list});
