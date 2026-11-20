#!/usr/bin/env python3
"""对指定 PCB 文档运行 DRC，输出各类错误计数与非 Connection 错误明细。

用法:
    python tools/eda_drc.py <pcbUuid>

期望: Clearance Error = 0（Connection Error 为未连线，属正常状态）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bridge_run import run  # noqa: E402

JS = r"""
const TARGET='__UUID__';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return JSON.stringify({__error:'ABORT: wrong document', current: (doc&&doc.uuid)||null});
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const cats = arr.map(c=>({name:c.name, n:(c.list||[]).reduce((s,sub)=>s+((sub.list?sub.list.length:0)),0)}));
const detail=[];
for(const cat of arr){
  if(String(cat.name).indexOf('Connection')>=0) continue;
  for(const s of (cat.list||[])){
    for(const it of (s.list||[]).slice(0,20)){
      detail.push({cat:cat.name, sub:s.name, o1:it.obj1Suffix, o2:it.obj2Suffix, d:(it.errData&&it.errData.minDistance)});
    }
  }
}
return JSON.stringify({cats, detail});
"""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    uuid = sys.argv[1]
    res, err = run(JS.replace('__UUID__', uuid), timeout=180)
    if err:
        print('ERROR:', err)
        sys.exit(1)
    data = json.loads(res)
    if isinstance(data, dict) and data.get('__error'):
        print('ERROR:', data)
        sys.exit(2)

    cats = data.get('cats') or []
    detail = data.get('detail') or []
    print('DRC 结果:')
    for c in cats:
        print(f"  {c['name']}: {c['n']}")
    non_conn = [c for c in cats if 'Connection' not in str(c['name'])]
    if non_conn:
        print('\n非 Connection 错误明细（最多 20 条/类）:')
        for d in detail:
            print(f"  [{d['cat']}] {d.get('sub')}  obj1={d.get('o1')} obj2={d.get('o2')} minD={d.get('d')}")
        print('\nFAIL: Clearance 等错误必须为 0，请按 objSuffix 定位修复后复验。')
        sys.exit(1)
    print('\nPASS: 仅存在 Connection Error（未连线，正常）。')


if __name__ == '__main__':
    main()
