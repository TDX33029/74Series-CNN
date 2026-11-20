const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const des = comps.map(c => c.getState_Designator()).filter(d => /^(LED|Q|R|RP|C)/.test(d));
const out = [];
for (const d of des) {
  const c = comps.find(k => k.getState_Designator() === d);
  const a = c.toAsync();
  const pins = await a.getAllPins();
  let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9;
  const nets = [];
  for (const p of pins) {
    xmin=Math.min(xmin,p.x); xmax=Math.max(xmax,p.x);
    ymin=Math.min(ymin,p.y); ymax=Math.max(ymax,p.y);
    nets.push({n:p.padNumber, net:p.net, dx:Math.round((p.x-c.getState_X())*10)/10, dy:Math.round((p.y-c.getState_Y())*10)/10, pad:p.pad});
  }
  out.push({des:d, x:Math.round(c.getState_X()*10)/10, y:Math.round(c.getState_Y()*10)/10, rot:c.getState_Rotation(), layer:c.getState_Layer(), hw:Math.round((xmax-xmin)/2*10)/10, hl:Math.round((ymax-ymin)/2*10)/10, pins:nets});
}
return JSON.stringify(out);
