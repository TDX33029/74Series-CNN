const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = comps.map(c => ({des: c.getState_Designator(), x: Math.round(c.getState_X()*10)/10, y: Math.round(c.getState_Y()*10)/10, rot: c.getState_Rotation(), layer: c.getState_Layer()}));
return JSON.stringify(out);
