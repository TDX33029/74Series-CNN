const TARGET='a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
// LED_DONE_ST_N 和 LEDP1 的实际焊盘范围 + LED右缘与板框
const comps = await eda.pcb_PrimitiveComponent.getAll();
const want = ['LED_DONE_ST_N','LEDP1','LED_CLK','LED_MC2','R2044','Q2022'];
const out=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(!want.includes(des)) continue;
  let pins=null;
  try{ pins = await c.toAsync().getAllPins(); }catch(e){}
  if(!pins){
    try{ pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId()); }catch(e){}
  }
  const rec={des};
  if(pins && pins.length){
    const xs=pins.map(p=>p.x), ys=pins.map(p=>p.y);
    rec.xmin=Math.min(...xs); rec.xmax=Math.max(...xs);
    rec.ymin=Math.min(...ys); rec.ymax=Math.max(...ys);
  } else rec.pins='none';
  out.push(rec);
}
return JSON.stringify(out);
