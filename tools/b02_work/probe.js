const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const c = comps.find(k => k.getState_Designator() === 'Q2001');
const a = c.toAsync();
const methods = [];
let o = a;
while (o && o !== Object.prototype) { methods.push(...Object.getOwnPropertyNames(o)); o = Object.getPrototypeOf(o); }
return JSON.stringify({methods: [...new Set(methods)].filter(m => /ayer|lip|irror|otation|_X|_Y/.test(m)), curLayer: a.getState_Layer ? a.getState_Layer() : 'NOFN'});
