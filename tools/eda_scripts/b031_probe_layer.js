// probe: setState_Layer on component, verify flips to backside
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const c = comps.find(k => k.getState_Designator() === 'RP1');
if (!c) return 'RP1 not found';
const a = c.toAsync();
const before = {layer: c.getState_Layer(), x: c.getState_X(), y: c.getState_Y()};
a.setState_Layer(2);
await a.done();
const c2 = comps.find(k => k.getState_Designator() === 'RP1');
const after = {layer: c2.getState_Layer(), x: c2.getState_X(), y: c2.getState_Y()};
// revert to front
const a2 = c2.toAsync();
a2.setState_Layer(1);
await a2.done();
const c3 = comps.find(k => k.getState_Designator() === 'RP1');
const reverted = {layer: c3.getState_Layer()};
return JSON.stringify({before, after, reverted});
