const TARGET='a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
// 若有 Clearance 类错误列出明细；只取前 12 条
const out=[];
for(const cat of arr){
  if(String(cat.name).indexOf('Connection')>=0) continue;
  const subs = cat.list||[];
  for(const s of subs){
    const items = s.list||[];
    for(const it of items.slice(0,12)){
      out.push({cat:cat.name, sub:s.name, suffix:it.suffix, d:it.errData && it.errData.minDistance, p:it.position});
    }
  }
}
return JSON.stringify({cats: arr.map(c=>c.name), details: out.slice(0,12)});
