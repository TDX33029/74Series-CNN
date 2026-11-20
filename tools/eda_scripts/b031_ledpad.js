const TARGET='d760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const comps = await eda.pcb_PrimitiveComponent.getAll();
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(!['LEDP1','LED_MEM_D7'].includes(des)) continue;
  const pins = await c.toAsync().getAllPins();
  const a=c.toAsync();
  return JSON.stringify({des, x:a.getState_X(), y:a.getState_Y(), rot:a.getState_Rotation(), pins:(pins||[]).map(p=>({pin:String(p.padNumber??'?'), x:p.x, y:p.y}))});
}
return 'not found';
