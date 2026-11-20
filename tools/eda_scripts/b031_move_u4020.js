// move U4020 to x=3050 y=-800 (make room for back Q/R columns)
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const c = comps.find(k => k.getState_Designator() === 'U4020');
if (!c) return 'U4020 not found';
const a = c.toAsync();
a.setState_X(3050); a.setState_Y(-800); a.setState_Rotation(90);
await a.done();
return 'U4020 moved to 3050,-800';
