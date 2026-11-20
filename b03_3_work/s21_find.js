const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const backPads = [], frontTH = [];
for (const c of comps) {
  const des = c.getState_Designator();
  const layer = c.getState_Layer();
  const a = c.toAsync();
  const pins = await a.getAllPins();
  for (const p of pins) {
    if (layer === 2) backPads.push({des, n: p.padNumber, x: p.x, y: p.y});
    else frontTH.push({des, n: p.padNumber, x: p.x, y: p.y});
  }
}
const bad = [];
for (const b of backPads) {
  for (const f of frontTH) {
    const cdist = Math.sqrt((b.x-f.x)**2 + (b.y-f.y)**2);
    if (cdist < 88) bad.push({b: b.des+'_'+b.n, f: f.des+'_'+f.n, d: Math.round(cdist*10)/10});
  }
}
return JSON.stringify(bad);
