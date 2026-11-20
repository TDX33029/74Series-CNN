const TARGET='a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const comps = await eda.pcb_PrimitiveComponent.getAll();
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(!['LED_DONE_ST_N','LEDP1','Q2022','R2043','R2044'].includes(des)) continue;
  const pins = await c.toAsync().getAllPins();
  const out=(pins||[]).map(p=>({pin:p.padNumber||p.pin||p.index, net:p.net||p.netName||'', x:p.x, y:p.y}));
  const a=c.toAsync();
  return JSON.stringify({des, x:a.getState_X(), y:a.getState_Y(), layer:a.getState_Layer(), pins:out});
}
return 'not found';
