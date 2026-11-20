const BOARD='B01_SUPERVISOR';
let bi=null;
try{ bi = await eda.dmt_Board.getBoardInfo(BOARD); }catch(e){ return 'ERR getBoardInfo:'+e.message; }
let pcbUuid = bi && bi.pcb && bi.pcb.uuid;
if(!pcbUuid){ return 'SHAPE:'+JSON.stringify(bi).slice(0,600); }
const d0 = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(!d0 || d0.uuid!==pcbUuid){
  try{ await eda.dmt_EditorControl.openDocument(pcbUuid); }catch(e){ return 'ERR open:'+e.message; }
}
const d1 = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(!d1 || d1.uuid!==pcbUuid) return 'ABORT: doc='+JSON.stringify(d1);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const g=(o,k)=>{try{return o['getState_'+k]();}catch(e){return undefined;}};
const out=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(!/^(LED|Q|R)\d+/.test(des)) continue;
  const a=c.toAsync();
  const rec={des, x:g(a,'X'), y:g(a,'Y'), rot:g(a,'Rotation'), layer:g(a,'Layer')};
  if(rec.x===undefined){ rec.x=g(c,'X'); rec.y=g(c,'Y'); rec.rot=g(c,'Rotation'); rec.layer=g(c,'Layer'); }
  out.push(rec);
}
let outline=null;
try{
  const pls=await eda.pcb_PrimitivePolyline.getAll();
  for(const p of pls){ if(p && p.polygon){ outline=p.polygon; break; } }
}catch(e){}
return JSON.stringify({doc:d1.uuid, outline:outline, n:out.length, comps:out});
