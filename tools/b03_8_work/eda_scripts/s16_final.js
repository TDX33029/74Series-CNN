const TARGET='c03b63553aa7180b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc.uuid!==TARGET) return 'ABORT: wrong document '+doc.uuid;
const pls=await eda.pcb_PrimitivePolyline.getAll();
const comps=await eda.pcb_PrimitiveComponent.getAll();
const j=comps.find(c=>c.getState_Designator()==='J20208');
return JSON.stringify({outline:pls.map(p=>({layer:p.getState_Layer(),polygon:p.polygon})),J:{x:j.getState_X(),y:j.getState_Y(),rot:j.getState_Rotation()}});
