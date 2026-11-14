# LED 模块快速创建方法（供任意对话/脚本调用）

更新：2026-11-13。来源：A000 板 `p1` 页的标准 LED 模块（LED + S8050 + 1k + 10k）。
实测速度：约 **8 秒/模块**（4 器件 + 7 导线 + 1 标签），远快于逐个手放。

现成脚本：`D:/tmp/jlc_brd/led_expand_prim.py`（可选板运行，自动跳过已达 20 颗的板）
方法文档：本文件。清理工具：`D:/tmp/jlc_brd/led_cleanup2.py`（按 `lm` 标记删除）。

---

## 0. 两条铁律（必须遵守，否则会写错页面）

1. **`setDocumentSource` 不能新增对象**，只能修改既有对象。新增器件/导线/文本
   必须用 Primitive API（`sch_PrimitiveComponent.create` 等）。
2. **所有 Primitive 写入都作用于"当前活动页"**。如果工程被另一个对话同时操作，
   活动页会被切走，对象就会创建到错误的板上（本次事故的根源）。
   因此：**每个模块创建前，必须在同一段 JS 里校验
   `eda.dmt_SelectControl.getCurrentDocumentInfo().uuid === 目标页uuid`**，
   不匹配立即中止返回。一次 bridge 调用只处理一个页面。

## 1. 器件来源（lib_Device.search 后按 uuid 取用）

| 角色 | search 关键字 | device uuid | 备注 |
|---|---|---|---|
| LED | `HLMP-S301` | `63d066375075417d84316cf0ed4f9148` | 插件黄灯，封装 LED-TH_L5.0-W2.0-RD |
| 三极管 | `S8050` | `19cbdd966f174763acafb09641d60f4c` | SOT-23，pin1=B, pin2=E, pin3=C |
| 电阻 | `Res_0402` | `91a2612de3e3479bbbf64adbcfa73f93` | 通用 0402 电阻，Value 为实例属性 |

注意：不要用 `{libraryUuid, uuid}` 精简对象直接 create（会挂起）；
要传 `lib_Device.search()` 返回的完整器件项。

## 2. 模块几何（相对模块锚点，API 坐标系 y 向上，单位 0.01inch）

器件（create 参数 x,y,rotation）：

```
LED : (60, 75) rot 270
Q   : (20, 45) rot 0
R1k : (60, 25) rot 90   Value='1kΩ'      → +VLED 限流
R10k: ( 0, 65) rot 90   Value=10k/47k/100k → 基极电阻
```

导线（`sch_PrimitiveWire.create([x1,y1,x2,y2], net)`，坐标=锚点+偏移）：

```
(30,15)-(30,25)  net='GND'    Q.e → GND
(60,45)-(60,55)  net=''       R1k 下端 → LED 上端
(30,95)-(30,65)  net=''       Q.c → 拐角
(60,95)-(30,95)  net=''       拐角 → LED 下端
(60, 0)-(60, 5)  net='+VLED'  R1k 上端 → +VLED
(10,45)-( 0,45)  net=''       Q.b → R10k 上端
( 0,90)-( 0,85)  net=控制网络  R10k 下端 → 被指示信号
```

标签：`sch_PrimitiveText.create(ax, ay+105, 网络短名, 0, null, null, 12, false, false, false, 3)`

## 3. 单模块创建 JS（核心片段）

```javascript
async function dev(kw,uuid){const h=await eda.lib_Device.search(kw)||[];
  return h.find(d=>d.uuid===uuid)||h[0];}
const dLED=await dev('HLMP-S301','63d066375075417d84316cf0ed4f9148');
const dQ  =await dev('S8050','19cbdd966f174763acafb09641d60f4c');
const dR  =await dev('Res_0402','91a2612de3e3479bbbf64adbcfa73f93');
// parts: [device, ox, oy, rot, 位号, UniqueID, Value?]
for(const [d,ox,oy,rot,des,uid,val] of parts){
  const c=await eda.sch_PrimitiveComponent.create(d, ax+ox, ay+oy, undefined, rot, false, true, true);
  const a=c.toAsync(); a.setState_Designator(des); a.setState_UniqueId(uid); await a.done();
  if(val){ // 电阻值是实例属性
    const attrs=await eda.sch_PrimitiveAttribute.getAll(c.getState_PrimitiveId())||[];
    for(const at of attrs) if(String(at.getState_Key())==='Value'){
      const aa=at.toAsync(); aa.setState_Value(val); await aa.done(); }
  }
}
// 然后 7 条 create 导线 + 1 条 create 文本
```

## 4. 批量流程（每块板）

1. **先扫描该板全部页面**（只读）：统计现有 `LED\d+` 数量、LED/Q/R 位号最大值；
   ≥20 直接跳过。同时追踪现有 LED 模块的被指示网络（Q 的基极导线 → 10k 电阻
   → 另一端导线的 NET），避免在同一网络上重复加灯。
2. **选主器件页**：没有 J 开头位号连接器的那一页（两页都有/都没有时取器件多
   的页）。**不要**放连接器页，也不要新建独立页。
3. **摆放位置**：取该页器件与导线的最大 X，`x0 = maxX + 150`，`y0 = 100`，
   4 列 × N 行，列距 150、行距 130（模块占 60×95，文本在上方 105）。
4. **位号分配**：在扫描得到的最大值之上递增（LED+1…，Q+1…，R+2/模块）。
5. **UniqueID**：统一用 `lm` 前缀 + 8 位 hex（全工程唯一）。这是清理标记，
   出问题可按 `Unique ID startsWith 'lm'` 一键删除。
6. **每 5 个模块一次 bridge 调用**（约 40s，超时设 280s）；每次调用开头与每个
   模块创建前都校验活动页 UUID，不匹配立即返回。
7. 全部完成后 `eda.sch_Document.save()`，并复核该板 LED 总数 ≥20。

## 5. 基极电阻取值（防总线过载）

- 被指示网络只在本板出现 → 10kΩ（灌入 ~0.43mA）
- 出现在 3–8 块板 → 47kΩ
- 出现在 >8 块板（CLK、DATA 等背板总线）→ **100kΩ**（47 板全挂也只 ~2mA）
- LED 电流由 1k 决定（~2.7mA），与基极电阻无关；100k 时 Ib≈43µA 仍饱和。

## 6. 清理方法（出问题时）

```javascript
// 删除某页上所有脚本创建的器件（Unique ID 以 lm 开头）
const cs=await eda.sch_PrimitiveComponent.getAll()||[];
const ids=cs.filter(c=>String(c.getState_UniqueId()||"").startsWith('lm'))
            .map(c=>c.getState_PrimitiveId());
await eda.sch_PrimitiveComponent.delete(ids);
// 孤儿导线：端点不接触任何剩余器件引脚的导线再删；文本按内容+区域删
```

完整清理脚本：`D:/tmp/jlc_brd/led_cleanup2.py`。


## 8. 血泪教训（2026-11-14 事故）

- **模块 +VLED 馈线必须是独立命名走线**（net='+VLED'，按名字与电源轨连接），
  严禁画到连接器符号的桩线行上——B03 型排针桩线带为 x 315–345 / 405–435、
  y 450–760，其他板同理（引脚桩线 30 单位外扩）。画上去会与桩线合并，
  把 +VLED 轨接到该引脚的状态信号上（+VLED 短路）。
- **不要往连接器页放模块**；主器件页摆放位置必须避开所有现有器件引脚桩线。
- 创建导线时若端点落在别的网络的原语上，create 会失败或被 EDA "吞并"改名；
  创建后必须回读形状复核（EDA 会把多段折线重排成乱序路径，产生对角线）。
- 单段 H/V 导线创建是稳定的；多点折线和 3 段以上的链式创建会被 EDA 重排，
  严禁使用。
- 所有脚本创建的对象用 Unique ID 前缀标记（本项目用 `lm`），便于一键清理。

## 7. 已知坑

- `create` 的 rotation/mirror 必须给真实值，否则引脚整体错位。
- 引脚坐标可能带半格值，导线端点必须用 `getAllPins()` 的原始坐标。
- 电阻的 Value 在实例 ATTR 上，不在器件上；必须单独 setState_Value。
- `sch_PrimitiveText.create` 偶发静默失败，批量后要复核文本数量。
- 同一工程禁止两个对话同时做批量写入。
