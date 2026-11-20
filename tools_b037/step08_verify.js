const TARGET = '046a237b7518687e';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const a = c.toAsync();
  const pins = await a.getAllPins();
  let pxmin=1e9,pxmax=-1e9,pymin=1e9,pymax=-1e9;
  for (const p of pins) { pxmin=Math.min(pxmin,p.x); pxmax=Math.max(pxmax,p.x); pymin=Math.min(pymin,p.y); pymax=Math.max(pymax,p.y); }
  out.push({des: c.getState_Designator(), x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer(),
            pxmin: Math.round(pxmin*10)/10, pxmax: Math.round(pxmax*10)/10, pymin: Math.round(pymin*10)/10, pymax: Math.round(pymax*10)/10});
}
return JSON.stringify(out);
