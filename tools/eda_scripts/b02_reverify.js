const TARGET='a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const res=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(['LED_DONE_ST_N','Q2022','R2043','R2044','LEDP1'].includes(des)){
    const a=c.toAsync();
    res.push({des, x:a.getState_X(), y:a.getState_Y(), layer:a.getState_Layer()});
  }
}
return JSON.stringify(res);
