const TARGET='a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const want=['LED_DONE_ST_N','Q2022','R2043','R2044'];
const res=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(!want.includes(des)) continue;
  let pins=null;
  try{ pins = await c.toAsync().getAllPins(); }catch(e){}
  const a=c.toAsync();
  res.push({des, x:a.getState_X(), y:a.getState_Y(), layer:a.getState_Layer(),
    pins:(pins||[]).map(p=>({pin:String(p.padNumber??p.pin??'?'), net:String(p.net??p.netName??'?'), x:p.x, y:p.y}))});
}
return JSON.stringify(res);
