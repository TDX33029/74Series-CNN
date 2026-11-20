const TARGET='a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const detail=[];
for(const cat of arr){
  if(String(cat.name).indexOf('Connection')>=0) continue;
  for(const s of (cat.list||[])){
    for(const it of (s.list||[]).slice(0,8)){
      detail.push({cat:cat.name, sub:s.name, d:it.errData&&it.errData.minDistance});
    }
  }
}
return JSON.stringify(arr.map(c=>({name:c.name,n:(c.list||[]).reduce((s,sub)=>s+(sub.list?sub.list.length:0),0)})) , null, 0) + ' DETAILS:' + JSON.stringify(detail);
