const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const c = comps.find(k => k.getState_Designator() === 'RP1');
const a = c.toAsync();
a.setState_X(3522); a.setState_Y(1062); a.setState_Rotation(0); a.setState_Layer(2);
await a.done();
return 'RP1@' + a.getState_X() + ',' + a.getState_Y() + ',L' + a.getState_Layer();
