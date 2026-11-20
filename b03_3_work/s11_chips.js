const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const udes = comps.map(c => c.getState_Designator()).filter(d => /^U/.test(d));
const out = [];
for (const des of udes) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  const pins = await a.getAllPins();
  let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
  const pd = [];
  for (const p of pins) {
    xmin=Math.min(xmin,p.x); xmax=Math.max(xmax,p.x);
    ymin=Math.min(ymin,p.y); ymax=Math.max(ymax,p.y);
    pd.push({n:p.padNumber, dx: Math.round((p.x-c.getState_X())*100)/100, dy: Math.round((p.y-c.getState_Y())*100)/100, pad: p.pad, net: p.net});
  }
  out.push({des, x:c.getState_X(), y:c.getState_Y(), rot:c.getState_Rotation(), layer:c.getState_Layer(), bbox:{xmin,xmax,ymin,ymax}, hw: Math.round((xmax-xmin)/2*100)/100, hl: Math.round((ymax-ymin)/2*100)/100, pins: pd});
}
return JSON.stringify(out);
