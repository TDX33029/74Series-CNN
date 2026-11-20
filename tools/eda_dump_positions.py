#!/usr/bin/env python3
"""导出指定 PCB 文档全部器件的位号/坐标/旋转/层，保存为 JSON。

用法:
    python tools/eda_dump_positions.py <pcbUuid> <out.json>

输出格式:
    [{"des":"U4001","x":540,"y":-700,"rot":90,"layer":1}, ...]
    layer: 1=正面(top)  2=背面(bottom)
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
const comps = await eda.pcb_PrimitiveComponent.getAll();
const g=(a,k)=>{try{return a['getState_'+k]();}catch(e){return null;}};
const out=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  const a=c.toAsync();
  out.push({des, x:g(a,'X'), y:g(a,'Y'), rot:g(a,'Rotation'), layer:g(a,'Layer')});
}
return JSON.stringify(out);
"""


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    uuid, out = sys.argv[1], sys.argv[2]
    res, err = run(JS.replace('__UUID__', uuid), timeout=60)
    if err:
        print('ERROR:', err)
        sys.exit(1)
    data = json.loads(res)
    if isinstance(data, dict) and data.get('__error'):
        print('ERROR:', data)
        sys.exit(2)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'saved {len(data)} components -> {out}')


if __name__ == '__main__':
    main()
