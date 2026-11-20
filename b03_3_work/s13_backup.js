const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = comps.map(c => ({des: c.getState_Designator(), x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer()}));
return JSON.stringify(out);
