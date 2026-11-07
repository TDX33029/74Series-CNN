# KiCad → 嘉立创EDA（专业版）原理图转换自述

> 最后更新：2026-11-06
> 适用工程：`74CNN`，已迁移 S01/S02/S04/S05 四张图页（S01 在 `Board1`，其余各自独立板子）
> 目标：把 KiCad 原理图完整迁移到嘉立创EDA（EasyEDA Pro），**只做原理图，不画 PCB**
> 源文件：`D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\S0{1,2,4,5}_*.kicad_sch`

---

## 0. 新对话 60 秒进入状态

1. 先读本文件，不要重新摸索 GUI。
2. 确认 Bridge 在跑：
   ```bash
   for p in $(seq 49620 49629); do
     r=$(curl -s --max-time 1 http://127.0.0.1:$p/health)
     echo "$r" | grep -q easyeda-bridge && echo "BRIDGE=$p" && break
   done
   ```
3. 确认 EDA 已连接（下面假设端口是 49620，实际用第 2 步找到的端口）：
   ```bash
   curl -s http://127.0.0.1:49620/eda-windows
   ```
   如果 `count=0`，见第 3 节“重连 EDA”。
4. 打开工程和图页（第 4 节代码），先核对第 2 节“现状快照”。
5. 改动前先 `eda.sch_Document.save()` 备份；改动后用第 8 节清单验证。

当前环境已确认可用：嘉立创EDA 桌面版 `V3.2.149.88089769` + `easyeda-api` Bridge。**不要用 GUI 自动化**（本机 computer-use 插件未启用），直接走 HTTP API。

### 绘图规则速查

- 只做原理图，**不画 PCB**。
- IC 全部 **PDIP**（14/16/20/28 脚）；电容/电阻用直插 `CAP-TH`/`RES-TH`；测试点 `TESTPOINT-TH`；排针 `HDR-TH`。
- **不要替换导入的符号**；只通过属性改封装，保住导入的导线和 no-connect。
- 本地标签补成**文本**（S01 221 / S02 79 / S04 828 / S05 348 条），网络名已写在导线上；不要用 `createNetLabel`。
- 全局标签、电源符号、图框必须 `addIntoBom=false / addIntoPcb=false`。
- 改完必须保存并核对（每张图的基准值见第 2 节汇总表）：`part` 数、`WIRE`、`TEXT`、`Footprint` 属性数、BOM 封装列非空。

---

## 1. 工具链

| 项 | 值 |
|---|---|
| Skill 安装目录 | `C:\Users\Lenovo\.zcode\skills\easyeda-api` |
| Bridge 启动 | `node C:\Users\Lenovo\.zcode\skills\easyeda-api\scripts\bridge-server.mjs` |
| Bridge 端口 | `49620–49629`，自动选第一个可用端口 |
| 健康检查 | `GET http://127.0.0.1:49620/health` |
| 执行接口 | `POST http://127.0.0.1:49620/execute`，body `{"code":"..."}` |
| EDA 端扩展 | `run-api-gateway`（已安装，`onStartupFinished` 自动连接） |
| 桌面端路径 | `C:\Program Files\lceda-pro\lceda-pro.exe` |

Bridge 超时是 **30 秒/请求**。大导入、导出、DRC 等操作可能超时；超时不代表 EDA 没执行完，重要操作建议“发起后轮询状态”。

### 执行代码的上下文

```js
async function(eda) {
  // 只写函数体
  // 必须 await 所有 Promise
  // 必须 return 结果；console.log 不会被返回
  // 不要写注释（代码可能被单行化）
  // 枚举用 EDMT_/ESCH_/EPCB_ 等枚举，不要猜数字
  return await eda.dmt_Project.getCurrentProjectInfo();
}
```

大请求（例如 800KB 的 base64）不要用 shell 拼字符串，写成 JSON 文件后：

```bash
curl -s --max-time 60 -X POST http://127.0.0.1:49620/execute \
  -H "Content-Type: application/json" \
  --data-binary "@D:/tmp/req.json"
```

---

## 2. 现状快照（2026-11-07）

S01–S17 中实际存在的 14 张图页均已导入 `74CNN` 并补齐封装；每页一个独立板子，均未绘制 PCB。S03/S14/S16 在源目录不存在（S14/S16 只在归档目录），不在本轮范围。

### 板子与图页

| 图页 | 板子名 | 板子 UUID | 图页 UUID |
|---|---|---|---|
| S01 | `Board1` | `f6e1d58ba3e70be1` | `547b02c6c6c922f8` |
| S02 | `S02_Timing_1` | `665fe4d752f6dd8b` | `974468c12991a54e` |
| S04 | `S04_Memories_1` | `46743cc936140e9b` | `757acc94a6335078` |
| S05 | `S05_Pool_1` | `c6d1d9bcb3c57a9d` | `a57a4c19d44c66b7` |
| S06 | `S06_Argmax_global` | `24869f1b8108c2c1` | `8cc388e8aea09808` |
| S07 | `S07_Conv1_global` | `21dcf2509dc906a7` | `d13a2a40be8055c9` |
| S08 | `S08_Conv2_global` | `51d36f134ab41500` | `89ce4c14faf644fd` |
| S09 | `S09_FC_global` | `e32b0802e6a01f02` | `1717e48e2c1cc77d` |
| S10 | `S10_Top_IO` | `1ea3b4aa13c97477` | `958657b114d1be68` |
| S11 | `S11_BusFabric` | `5edb529dff17e2fc` | `1eec14a9e1ffa167` |
| S12 | `S12_DataAssembly` | `668c6a8ea5e06dc7` | `59dc483730406f42` |
| S13 | `S13_Requant_C1` | `f71ec959be9fe9c7` | `98bc80eb6642ed01` |
| S15 | `S15_Requant_C2` | `68f3270929f356ce` | `2bdccc4358295850` |
| S17 | `S17_Requant_FC` | `e9325ff08299414d` | `64adbd3dae4fdb2f` |

> S06 在网表修复阶段用“局部标签转全局标签”的临时副本重新导入，旧板 `S06_Argmax` 已删除；S07/S08/S09 同样使用全局标签副本。源 `.kicad_sch` 未被修改。

### 14 张图页汇总

| 图页 | part | netport | netflag | 封装缺失 | 非器件 BOM/PCB 标记 | 网表对比 |
|---|---|---|---|---|---|---|
| S01 | 82 | 142 | 214 | 0 | 0 | 0 差异 |
| S02 | 37 | 50 | 98 | 0 | 0 | 0 差异 |
| S04 | 142 | 537 | 286 | 0 | 0 | 0 差异 |
| S05 | 166 | 188 | 303 | 0 | 0 | 0 差异 |
| S06 | 149 | 632 | 258 | 0 | 0 | 0 差异 |
| S07 | 197 | 2560 | 0 | 0 | 0 | 0 差异 |
| S08 | 193 | 2583 | 0 | 0 | 0 | 0 差异 |
| S09 | 179 | 2375 | 0 | 0 | 0 | 0 差异 |
| S10 | 85 | 182 | 111 | 0 | 0 | 0 差异 |
| S11 | 47 | 162 | 96 | 0 | 0 | 0 差异 |
| S12 | 18 | 162 | 33 | 0 | 0 | 0 差异 |
| S13 | 37 | 117 | 49 | 0 | 0 | 0 差异 |
| S15 | 36 | 115 | 49 | 0 | 0 | 0 差异 |
| S17 | 61 | 161 | 87 | 0 | 0 | 0 差异 |
| **合计** | **1429** | **9966** | **1584** | **0** | **0** | **14/14 通过** |

> 网表对比按“引脚分区”判定（忽略网络名与 KiCad `unconnected-*`），KiCad 与 EDA 的网络数、引脚数、每个引脚所在网络集合全部一致；详见根目录 `NETLIST_COMPARE_REPORT.md`。KiCad 网络名的层级前缀 `/` 在 EDA 中不带，仅影响名称、不影响连通性。

### 封装映射（全工程通用，DIP/直插优先）

| 器件 | 封装实例 UUID | 封装名 |
|---|---|---|
| 74HC74 / 74HC04 / 74HC08 / 74HC32 / 74HC02 | `5fbc27e5b47b1d75` | `PDIP-14_L19.3-W6.4-P2.54-LS7.6-BL` |
| 74HC161 / 74HC238 / 74HC157 / 74HC283 / 74HC85 | `cbab301e5fcc9cfe` | `PDIP-16_L19.3-W6.4-P2.54-LS7.9-BL` |
| 74HCT273 / 74HCT574 / 74HCT541 / 74HC688 / 74HC245 | `96709c1c96c0dc46` | `PDIP-20_L24.5-W6.4-P2.54-LS7.9-BL` |
| 27C512 / 28C256 / HY6264AxP | `5e745cbf9aa52a38` | `PDIP-28_L37.0-W13.5-P2.54-LS15.6-BL` |
| 电容 C | `a6acf80ecb70dfc9` | `CAP-TH_L5.0-W2.5-P5.00-D1.0` |
| 电阻 R | `b080637a828494eb` | `RES-TH_L6.2-W2.3-LR1F1K0` |
| 测试点 TP | `be47545c61f5a966` | `TESTPOINT-TH_BD2.0-D1.0` |
| 排针 2×20 | `28846765b72b82e7` | `HDR-TH_40P-P2.54-V-R2-C20-S2.54-1` |
| 排针 2×16 / 2×12 / 2×10 / 2×2 / 1×2 / 1×3 | 见 `tools/jlc/jlc_batch.py` 的 `FP` 映射 | 直插排针 |
| LED / 晶振 / 按键 / 排阻 | 见 `tools/jlc/jlc_batch.py` 的 `FP` 映射 | 直插 |

> 1429 个实体单元全部有封装（覆盖率 100%）；所有 netport/netflag/text/sheet 等非器件对象均已 `Add into BOM = no`、`Convert to PCB = no`。

---

## 3. 启动 / 重连 EDA

### 3.1 启动 Bridge（后台）

```bash
cd C:\Users\Lenovo\.zcode\skills\easyeda-api
node scripts/bridge-server.mjs
```

必须后台运行，不要前台阻塞。首次使用先 `npm install`（依赖只有 `ws`）。

### 3.2 重连 EDA 窗口

EDA 窗口断开（`EDA window "..." disconnected`）时，**再启动一次桌面端**会由单实例逻辑新开一个编辑器窗口，扩展会重新握手：

```powershell
Start-Process -FilePath 'C:\Program Files\lceda-pro\lceda-pro.exe'
```

等约 12 秒：

```bash
curl -s http://127.0.0.1:49620/health
curl -s http://127.0.0.1:49620/eda-windows
```

`windowId` 会变化，这是正常的；Bridge 只有一个窗口时会自动选为 active。重连后必须重新 `openProject` + `openDocument`（第 4 节）。

### 3.3 不要做的事

- 不要用 PowerShell/UI Automation 去点菜单；当前会话没有 CUA 权限。
- 不要重启整个 EDA 进程去“修复”连接，优先“再启动一次”开新窗口。
- 不要随便关窗口；Bridge 连接会跟着断。

---

## 4. 打开工程与图页

```js
const opened = await eda.dmt_Project.openProject("6b7464fb399341afac3f4452db9da3df");
await new Promise(r => setTimeout(r, 3500));
const tabId = await eda.dmt_EditorControl.openDocument("37c4598aec0b2ec1");
await eda.dmt_EditorControl.activateDocument(tabId);
await new Promise(r => setTimeout(r, 1200));
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return { opened, tabId, doc };
```

期望：`doc.documentType === 1`（原理图页），`doc.uuid === "37c4598aec0b2ec1"`。

> `openProject` 可能丢弃当前未保存修改；调用前先保存。
> `openDocument` 可能触发新窗口/重载，`windowId` 变化后重连即可。

---

## 5. KiCad → 嘉立创EDA 导入流程（已跑通）

### 5.1 原理

嘉立创EDA 自带的 KiCad 导入接口：

```js
eda.sys_FileManager.importProjectByProjectFile(
  file,                    // File 对象，内容是 .kicad_sch
  "KiCad",
  { importOption: "ImportDocument" },          // 只导文档，不抽取库
  { operation: "Existing Project",
    existingProjectUuid: "6b7464fb399341afac3f4452db9da3df" }
);
```

**注意：导入到已有工程时，它不会写入现有 Board1 的图页，而是新建一个同名板子**（`S01_Supervisor`）和一张新原理图页。正确做法是“先导入 → 再复制图页 → 再删临时板子”。

### 5.2 文件如何送进 EDA

EDA 运行在浏览器上下文，不能读本地路径。把 `.kicad_sch` 读成 base64 塞进代码：

```js
const b64 = "...";                       // 约 805KB
const bin = atob(b64);
const bytes = new Uint8Array(bin.length);
for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
const file = new File([bytes], "S01_Supervisor.kicad_sch", { type: "application/octet-stream" });
const p = await eda.sys_FileManager.importProjectByProjectFile(
  file, "KiCad", { importOption: "ImportDocument" },
  { operation: "Existing Project", existingProjectUuid: "6b7464fb399341afac3f4452db9da3df" }
);
return p;
```

导入 602KB 文件约 1–2 秒；测试工程导入后再导入 74CNN 均可成功。

### 5.3 导入后清理步骤（必须）

1. 记录导入产生的新板子/新原理图/新图页：
   ```js
   const boards = await eda.dmt_Board.getAllBoardsInfo();
   return boards;
   ```
   新板子通常叫 `S01_Supervisor`，其 `schematic.page[0].uuid` 是源图页。
2. 把源图页复制到目标 `Board1` 的原理图：
   ```js
   const newPage = await eda.dmt_Schematic.copySchematicPage(
     "<源图页UUID>",
     "42f7d523ec754384"        // Board1 的 s01_supervisor
   );
   ```
3. 验证目标图页里有内容：
   ```js
   await eda.dmt_EditorControl.openDocument("37c4598aec0b2ec1");
   const comps = await eda.sch_PrimitiveComponent.getAll();
   const wires = await eda.sch_PrimitiveWire.getAll();
   return { comps: comps.length, wires: wires.length };
   ```
4. 删除导入产生的临时板子（连带它的原理图）：
   ```js
   await eda.dmt_Board.deleteBoard("S01_Supervisor");
   ```
5. 删除 Board1 原有的空图页 `p1`（如果还在）：
   ```js
   await eda.dmt_Schematic.deleteSchematicPage("761e790a17703b81");
   ```
6. 保存：
   ```js
   await eda.sch_Document.save();
   ```

> `deleteBoard` 只删板子和它的原理图，不会回头删已复制到 Board1 的图页。

---

## 6. 导入后的“补画”规则

### 6.1 坐标映射（KiCad mm → EasyEDA 0.01inch）

```
X_easy = X_mm / 0.254
Y_easy = -Y_mm / 0.254
```

例：KiCad `(at 54.61 80.01)` → EasyEDA `(215, -315)`。

### 6.2 本地标签（`(label ...)`）

嘉立创EDA 导入器**不会把本地标签画出来**，只把网络名写到导线上（`WIRE.net`）。图面看起来会缺标签，因此要按数量补文本（S01 221 条、S02 79 条、S04 828 条、S05 348 条）：

- 位置：标签锚点 + 垂直偏移 `+3`（单位 0.01inch，放在导线上方）；
- 旋转：KiCad 0/180 → EasyEDA `rotation=0`；KiCad 90/270 → `rotation=90`，并 `x+3`；
- 对齐：KiCad `justify right` → `alignMode=8`（RIGHT_MIDDLE）；`justify left` → `alignMode=2`（LEFT_MIDDLE）；
- 字号：`5.90551`；
- 文本用 `eda.sch_PrimitiveText.create(...)`，**直接传 2/8 即可**。S02/S04/S05 实测：`create(2)` 回读 `getAll().alignMode=4`（源码 `LEFT_MIDDLE`），`create(8)` 回读 `6`（源码 `RIGHT_MIDDLE`），与 KiCad 源逐条一致。
- **不要事后 `modify({alignMode})`**：部分取值会写坏对齐（出现 26、`NaNRIGHT_MIDDLE`、`align:null`）。先建 5 条抽样回读，正确就继续批量；只有抽样错误时才小范围试 modify，确认能修正后再全量。

```js
await eda.sch_PrimitiveText.create(X, Y, "NET_NAME", rotation, null, null, 5.90551,
  false, false, false, alignMode);   // alignMode: 2=left, 8=right
// 创建后可用源码回读核对 align 字段，不要默认再 modify
```

> `eda.sch_PrimitiveAttribute.createNetLabel()` 在当前客户端 **返回 undefined，实际不可用**，不要指望它。
> 因此本地标签是“文本”而不是真正的 net label；电气网络名已由导线 `net` 属性保证，不影响连通性。

批量创建时**不要在每批请求里调用 `openDocument`**：页面已经激活时它可能挂起 30 秒以上甚至一直不返回。正确做法：

1. 用一次 `jlc_batch.py activate`（或手动 `openDocument` + `activateDocument`）把目标页设为当前页；
2. 之后每批只做 `getAll` 去重 + `create`，每批 15–20 条；
3. 超时后先查 `TEXT` 总数，再重跑同一批；去重键用 `content|x|y`，不会重复。

### 6.3 全局标签 / 电源符号 / 图框

导入后它们是 `componentType` 为 `netport` / `netflag` / `sheet` 的图元，**不是实体器件**：

- 必须设 `addIntoBom=false`、`addIntoPcb=false`，否则 BOM 会混入 77 个全局标签和 214 个电源符号；
- `sch_PrimitiveComponent.modify()` 会拒绝非 `part` 类型，必须走 async setter：
  ```js
  const a = c.toAsync();
  a.setState_AddIntoBom(false);
  a.setState_AddIntoPcb(false);
  await a.done();
  ```

### 6.4 不要替换符号

导入的符号几何与 KiCad 一致，80 个实体元件的引脚落点已经与 512 根导线对齐。**不要为了换封装去删除/重建符号**，否则引脚坐标变化会破坏连线。封装通过修改属性完成（第 7 节）。

---

## 7. 封装规则（DIP 优先）

### 7.1 关键结论

- 只改 `part` 类型元件的 `otherProperty.Footprint`。
- **必须使用“工程封装实例 UUID”，不能用系统库 UUID。**
  - 用系统库 UUID（如 `228b21b1...`）：`footprint` 只有 `{uuid}`，BOM/属性面板封装列为空。
  - 用工程实例 UUID：`footprint` 变成 `{uuid, libraryUuid, name}`，BOM 正常显示封装名。
- 工程封装实例的获取方式：**临时放一个使用该封装的库器件 → 读取它的 `footprint` → 删掉器件**。封装副本会留在工程库，可复用。
- `lib_Footprint.copy(...)`、`lib_Footprint.create("project", ...)`、`getDocumentsource()` 在当前客户端均不可用/返回空，不要浪费试错。

### 7.2 获取工程封装实例（harvest）

```js
const d = (await eda.lib_Device.search("SN74HC74N")).find(x => x.name === "SN74HC74N");
const tmp = await eda.sch_PrimitiveComponent.create(
  { libraryUuid: d.libraryUuid, uuid: d.uuid }, 12000, -4000
);
const projectFp = tmp.footprint;   // { uuid, libraryUuid, name }
await eda.sch_PrimitiveComponent.delete([tmp.primitiveId]);
return projectFp;
```

已 harvest 的 6 种封装见第 2 节表格，可直接复用，不要再临时放器件。

### 7.3 给元件赋封装

```js
const props = Object.assign({}, c.otherProperty || {}, { Footprint: PROJECT_FP_UUID });
await eda.sch_PrimitiveComponent.modify(c.primitiveId, { otherProperty: props });
```

**`PROJECT_FP_UUID` 必须是 UUID 字符串，不能是 `{uuid, libraryUuid, name}` 对象**。传对象会得到 `footprint.uuid="[object Object]"`、`name` 为空，BOM 封装列空白；传字符串才会解析成完整 `{uuid, libraryUuid, name}`。

注意：

- 先 `getAll()` 拿最新的 `otherProperty` 再合并，`modify` 会整体替换属性表；
- 赋值后 `get()` 复核 `footprint.uuid === PROJECT_FP_UUID` 且 `footprint.name` 非空；
- 多单元器件（74HC74/04/08/32 等）每个 unit 都要设，同一个封装 UUID 可重复使用；
- 如果某个元件属性被误清空（如 U1001 的 Value），用同型号元件的 `otherProperty` 整体拷回。

### 7.4 当前封装映射（不要随意改）

| 元件名（`component.name`） | 封装实例 UUID |
|---|---|
| `74xx_74HC74` / `74xx_74HC04` / `74xx_74HC08` / `74xx_74HC32` | `5fbc27e5b47b1d75` |
| `74xx_74HC161` / `74xx_74HC238` / `74xx_74HC157` | `cbab301e5fcc9cfe` |
| `74xx_74HCT273` / `74xx_74HCT574` / `74xx_74HCT541` / `74xx_74HC688` | `96709c1c96c0dc46` |
| `Memory_EPROM_27C512` | `5e745cbf9aa52a38` |
| `Device_C` | `a6acf80ecb70dfc9` |
| `Connector_TestPoint` | `be47545c61f5a966` |

### 7.5 S02 / S04 / S05 追加封装映射

| 元件 | 封装实例 UUID | 封装名 |
|---|---|---|
| `74xx_74HC02` | `5fbc27e5b47b1d75` | `PDIP-14_L19.3-W6.4-P2.54-LS7.6-BL` |
| `74xx_74HC138` / `74xx_74HC283` / `74xx_74HC85` | `cbab301e5fcc9cfe` | `PDIP-16_L19.3-W6.4-P2.54-LS7.9-BL` |
| `74xx_74HC245` | `96709c1c96c0dc46` | `PDIP-20_L24.5-W6.4-P2.54-LS7.9-BL` |
| `Memory_EEPROM_28C256` / `Memory_RAM_HY6264AxP` | `5e745cbf9aa52a38` | `PDIP-28_L37.0-W13.5-P2.54-LS15.6-BL` |
| `Device_R` | `b080637a828494eb` | `RES-TH_L6.2-W2.3-LR1F1K0` |
| `Connector_Generic_Conn_02x12_Odd_Even` | `255c0e5285ea710d` | `HDR-TH_24P-P2.54-V-M-R2-C12-S2.54-2` |

> R 与 24P 排针的工程封装实例已预先 harvest，可直接使用，不必再临时放器件。

### 7.7 S06–S17 追加封装映射（2026-11-07 已 harvest）

| 元件 | 封装实例 UUID | 封装名 |
|---|---|---|
| `74xx_74HC00` | `5fbc27e5b47b1d75` | PDIP-14 |
| `74xx_74HC238` / `74xx_74LS148` | `cbab301e5fcc9cfe` | PDIP-16 |
| `74xx_74HCT245` | `96709c1c96c0dc46` | PDIP-20 |
| `Device_R_Network08` | `51b71e540536fb08` | `HDR-TH_9P-P2.54-V-F-1`（9 脚 SIP 替身） |
| `Connector_Generic_Conn_02x20_Odd_Even` | `28846765b72b82e7` | `HDR-TH_40P-P2.54-V-R2-C20-S2.54-1` |
| `Connector_Generic_Conn_02x16_Odd_Even` | `aba78d165edefae4` | `CONN-TH_32P-P2.54_C9900010108` |
| `Connector_Generic_Conn_02x10_Odd_Even` | `1e33bd087f44856a` | `HDR-TH_20P-P2.54-V-M-R2-C10-S2.54` |
| `Connector_Generic_Conn_02x02_Odd_Even` | `07c1f5b6a34479c1` | `HDR-TH_4P-P2.54-V-F-R2-C2-S2.54` |
| `Connector_Generic_Conn_01x02` | `97a28fdcd7a0e05b` | `HDR-SMD_2P-P2.54-V-F-LS4.9`（SMD 替身） |
| `Connector_Generic_Conn_01x03` | `654bb2be0d497120` | `HDR-TH_PM2.54-1X3PZZ-H8.5` |
| `Device_LED` | `b5b6ab5625dae23f` | `LED-TH_BD5.0-P2.54-L-RD_GREEN` |
| `Oscillator_ASE-xxxMHz` | `1bf2b016f2786394` | `CRYSTAL-SMD_4P-L3.2-W2.5-BL` |
| `Switch_SW_Push` | `dfb55335d44b6e80` | `SW-SMD_4P-L6.2-W6.2-P4.50-LS8.6`（SMD 替身） |

> 1x2、2x2、2x10、开关、晶振的库器件只有 SMD 封装可选，已作为替身；2x20/2x16/2x12/2x10/1x3/LED 为通孔。若后续找到更合适的 TH 封装，只改对应 UUID 即可，不影响电气。

### 7.6 辅助脚本

`tools/jlc/kicad_to_jlc.py`（本地 Python，不经过 EDA）：

```bash
python -I tools/jlc/kicad_to_jlc.py labels    S02_Timing.kicad_sch   D:/tmp/s02_labels.json
python -I tools/jlc/kicad_to_jlc.py importreq S02_Timing.kicad_sch   6b7464fb399341afac3f4452db9da3df D:/tmp/s02_import.json
python -I tools/jlc/kicad_to_jlc.py inventory S02_Timing.kicad_sch
```

- `labels` 输出 `[[X,Y,NAME,ROT,ALIGN], ...]`，X/Y 已按 0.254 换算，创建文本时再加 `+3` 偏移；
- `importreq` 生成带 base64 的 `/execute` 请求体；
- `inventory` 打印 `lib_id` 统计。

---

## 8. 验证清单（改完必跑）

### 8.1 数量与封装

```js
const c = await eda.sch_PrimitiveComponent.getAll();
const parts = c.filter(x => x.componentType === "part");
const noFp = parts.filter(p => !(p.footprint && p.footprint.name)).map(p => p.designator);
const noVal = parts.filter(p => !p.otherProperty || !p.otherProperty.Value).map(p => p.designator);
const badFlags = c.filter(x => x.componentType !== "part" && (x.addIntoBom || x.addIntoPcb));
return { total: c.length, parts: parts.length, noFp, noVal, badFlags: badFlags.length };
```

期望：

```
total=372, parts=80, noFp=[], noVal=[], badFlags=0
```

### 8.2 引脚—导线几何连通

```js
const wires = await eda.sch_PrimitiveWire.getAll();
const pts = new Set();
const add = (x, y) => pts.add(Math.round(x * 1000) / 1000 + "," + Math.round(y * 1000) / 1000);
for (const w of wires) { const L = w.line; add(L[0], L[1]); add(L[2], L[3]); }
const comps = await eda.sch_PrimitiveComponent.getAll();
let pins = 0, matched = 0, nc = 0;
for (const c of comps) {
  if (c.componentType !== "part") continue;
  const ps = await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.primitiveId);
  for (const p of ps) {
    pins++;
    const key = Math.round(p.x * 1000) / 1000 + "," + Math.round(p.y * 1000) / 1000;
    if (pts.has(key)) matched++;
    else if (p.noConnected) nc++;
  }
}
return { pins, matched, nc };
```

期望：`pins=813`（只统计 `part`，不含 7 个标签伪引脚）、`matched=794`、`nc=19`；`matched + nc = 813`。若把 77 个全局标签的 7 个伪引脚也算上，总引脚数是 820。

### 8.3 BOM

```js
const f = await eda.sch_ManufactureData.getBomFile("S01_bom", "csv");
return await f.text();
```

期望 14 行分组，`Footprint` 列全部非空，且不出现 `netport/netflag`。

### 8.4 保存并回读

```js
await eda.sch_Document.save();
const src = await eda.sys_FileManager.getDocumentSource();
return {
  len: src.length,
  fpAttrs: (src.match(/"key":"Footprint"/g) || []).length,
  text: (src.match(/"type":"TEXT"/g) || []).length,
  comp: (src.match(/"type":"COMPONENT"/g) || []).length
};
```

期望：`fpAttrs=80`、`text=226`、`comp=372`。

### 8.5 网表对比（所有图页绘制完成后）

**KiCad 侧**（不改源文件）：

```bash
"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist \
  --format kicadsexpr -o D:/tmp/jlc_netlist/S01_kicad.net \
  Cache/CNN_74xx_System/S01_Supervisor.kicad_sch
```

**EDA 侧**（先打开并激活对应图页）：

```js
const f = await eda.sch_ManufactureData.getNetlistFile("S01_net", "Protel2");
return await f.text();   // 非空字符串
```

> 实测 `getNetlist("EasyEDA")` 极慢；`getNetlist("Protel2")` 在多数页面可用，但 S06 等页面会返回 `null`，而 `getNetlistFile(...,"Protel2")` 仍能正常导出。统一用文件接口最稳。
> Bridge 的 `REQUEST_TIMEOUT_MS` 已从 `30000` 调到 `180000`（`C:\Users\Lenovo\.zcode\skills\easyeda-api\scripts\bridge-server.mjs`）；如果重装 Skill 后被还原，需要改回 180000 并重启 Bridge。

**三个已踩过的导入坑**：

- **电源命名分裂**：KiCad 电源符号导入成 netflag 后 `Name` 是 `power_+5V` / `power_GND`，而背板排针的 netport 叫 `+5V` / `GND`；EDA 按名字分网，必须把 `#PWR*` 的 `Name` 去掉 `power_` 前缀。
- **重叠导线/标签桩线**：导入器会把 KiCad 中重叠但无公共端点的导线合并成折线，或给浮动标签生成跨过相邻电源引脚的桩线，造成 +5V/GND 短路。对比发现某页电源脚数量异常偏多时，先查这两种几何。
- **电源桩线的巨型冗余标签**：导入器会给每条“引脚 → 电源符号”的桩线额外生成一个 `NET` 文字标签，字号直接写入 5 mm 的换算值 `196.85`，渲染成覆盖整页的 `power_+5V` / `power_GND` 大字；桩线另一端的 netflag/netport 已经承担网络名，该标签是冗余的。核对导线端点确有同名 netflag/netport 后，从文档源删除对应 `ATTR`；另有根级 `_NETLABEL_` 浮空标签一并删除。检查方法：遍历 `ATTR`，看 `fontSize > 20` 且 `value` 含 `power_`。

**比较方法**：

1. 两份网表都归一到 `REF.PIN` 引脚集合；多单元器件共用 `REF`，用不同 `PIN` 区分。
2. **只比较连通关系**（哪些引脚在同一网），忽略自动生成的网络名；网络名差异单独列 warning。
3. 检查五类问题：引脚缺失/多余、同一网被拆开、多个网被合并、引脚接错网、no-connect 被连接。
4. 电源/地（GND、+5V）和全局标签网络必须参与比较。
5. 每次修复后 `save()` → 重新导出两份网表 → 重新比较，直到连接差异为 0。
6. 若 KiCad 源本身就连错，标注“源设计问题”，不要为了对齐把 EDA 改成错误连接。

比较结果写入 `NETLIST_COMPARE_REPORT.md`，每页记录 KiCad 网络数、EDA 网络数、匹配数、修复项、剩余差异。

### 8.6 崩溃恢复与保存节奏

大批量操作（尤其 `netport/netflag` 的 async setter）可能让 EDA 渲染进程崩溃。崩溃后**未 `save()` 的改动会回滚到上一次保存**。

必须按阶段保存：

1. 封装全部赋完后立即 `eda.sch_Document.save()`；
2. 本地标签全部建完后立即 save；
3. 排除非实体图元时每 5–10 批 save 一次（每批 40 个），不要等全部跑完；
4. 每页收尾再 save 一次。

崩溃恢复步骤：

1. 关掉所有 `lceda-pro` 进程，重新启动**一个**实例；
2. `openProject` 后等 8–10 秒再查板子；
3. 打开该页，核对 `parts/texts/noFp/badNon`；
4. 只补缺失的阶段（封装看 `noFp`，标签看 `TEXT` 数量，排除看 `badNon`），不要重新导入。

---

## 9. 已踩过的坑（直接跳过）

| 现象 | 原因 / 处理 |
|---|---|
| `eda.dmt_Project.deleteProject()` 返回 `false` | 当前客户端是空实现，无法删工程；临时工程只能手动删 |
| `createNetLabel()` 返回 `undefined` | 当前客户端不可用；用 `sch_PrimitiveText.create` 补标签 |
| `modifySchematicPageTitleBlock()` 卡住 30s | 会挂起，不要调用；标题栏 Title/Date/Rev 暂时留空 |
| `sch_ManufactureData.getPngFile()` 不存在 | 用 `getExportDocumentFile` 也会卡住；不要靠截图验证 |
| `sch_Drc.check()` 30s 超时 | DRC 对大图很慢；用 8.2 几何连通 + BOM 校验代替 |
| `lib_Footprint.copy()` / `create("project")` 返回空 | 当前客户端不可用；用第 7.2 节 harvest |
| `lib_Footprint.get(uuid)` 报错 | 必须传第二参数系统库 UUID `0819f05c4eef4c71ace90d822a990e87` |
| `modify()` 报“仅当器件类型为元件时…” | `netport/netflag/sheet` 不能用 modify；用 `toAsync()` setter |
| 封装列在 BOM 为空 | 用了系统库 UUID；换成工程实例 UUID |
| 改了属性后 Value 变空 | `otherProperty` 整体替换导致；用同型号元件属性整体拷贝 |
| `EDA window ... disconnected` | 重新启动一次 `lceda-pro.exe` 开新窗口；重新打开工程/图页 |
| BOM 里出现 `U?` / 临时器件 | harvest 后忘记删；`sch_PrimitiveComponent.delete([id])` 并复核 `getAll()` |
| 文本标签对齐不对 | `create` 忽略 `alignMode`；创建后 `modify` 修正 |
| 图页重复 / 板子重复 | 导入到已有工程会新建板子；按 5.3 清理 |
| 页面外/页面上方出现大量错位网络标签 `bulktext*` | 导入时文本源坐标 `y` 写成了 live 值；文档源中把该 `TEXT` 的 `y` 取反即可 |
| 整页被 `power_+5V` / `power_GND` 大字覆盖 | 电源桩线上多了字号 `196.85` 的 `NET` 标签；确认导线另一端有同名 netflag/netport 后从文档源删除该 `ATTR`，不要只改字号（会留下重复小标签） |

---

## 10. 常用片段

### 列出所有板子

```js
return await eda.dmt_Board.getAllBoardsInfo();
```

### 列出所有图页

```js
return await eda.dmt_Schematic.getAllSchematicPagesInfo();
```

### 当前文档

```js
return await eda.dmt_SelectControl.getCurrentDocumentInfo();
```

### 统计元件类型

```js
const c = await eda.sch_PrimitiveComponent.getAll();
const m = {};
for (const x of c) {
  const t = x.componentType;
  m[t] = (m[t] || 0) + 1;
}
return m;
```

### 保存

```js
await eda.sch_Document.save();
```

---

## 11. 遗留事项

- **临时测试工程 `S01_import_test`**（UUID `bcd9afd42f5c446a8a44c8c930b9ae8b`）还在个人账号里；API 无法删除，需要手动在 EDA 开始页删除。
- 14 张图页的图框标题栏 `Title/Date/Rev` 均未写入（导入不带，API 会卡），标题栏为空。
- S01 在 `Board1`；其余 13 页各自独立板子（名单见第 2 节），没有 PCB，也没有合并到 Board1。
- 原理图页名是小写（`s01_supervisor` / `s02_timing` / `s04_memories` / …）；板名有 `_1` / `_global` 后缀。如需统一命名，用 `modifySchematicPageName` / `dmt_Board.modifyBoardName`，改前确认不影响引用。
- S06 旧板 `S06_Argmax` 已在网表修复后删除，当前板为 `S06_Argmax_global`（`24869f1b8108c2c1` / 图页 `8cc388e8aea09808`）。
- Bridge 是会话级后台进程；新会话需要按第 3.1 节重新启动。
- 所有 PCB 仍为空白（只有 Board1 有一个空 PCB），未画任何走线/器件。

---

## 12. 变更记录

| 日期 | 内容 |
|---|---|
| 2026-11-06 | 安装 `easyeda-api` Skill；用 Bridge 导入 `S01_Supervisor.kicad_sch` 到 74CNN/Board1；补 221 个本地标签文本；80 个实体元件赋 DIP/直插封装；排除 292 个非实体图元；保存并验证 |
| 2026-11-06 | 子代理导入 `S02_Timing.kicad_sch` → 新板 `S02_Timing`；36 个实体、79 标签、161 图元、203 WIRE、11 NC；封装 36/36 |
| 2026-11-06 | 子代理导入 `S04_Memories.kicad_sch` → 新板 `S04_Memories`；123 个实体、828 标签、600 图元、1303 WIRE、13 NC；封装 123/123 |
| 2026-11-06 | 子代理导入 `S05_Pool.kicad_sch` → 新板 `S05_Pool`；138 个实体、348 标签、511 图元、720 WIRE、32 NC；封装 138/138 |
| 2026-11-07 | 增加定时任务：每半小时检查 `Signal.txt`；完成后同步/补画 S01–S17，再逐页导出 EDA 与 KiCad 网表做引脚级连通对比并修复差异；Bridge 超时调到 180 秒，新增 8.5 节 |
| 2026-11-07 | 完成 14 张图页（S01/S02/S04–S13/S15/S17）重绘：1429 个实体、9966 个 netport、1584 个 netflag；封装覆盖 100%，非器件 BOM/PCB 标记清零 |
| 2026-11-07 | 网表对比 14/14 通过（0 引脚分区差异）。修复三类问题：① `power_+5V`/`power_GND` 与 `+5V`/`GND` 命名分裂；② S04 重叠导线把 +5V/GND 短接；③ S06 标签桩线跨过电源引脚，`/BYTE3`、`/FIRST` 误并到电源 |
| 2026-11-07 | S06 用全局标签临时副本重新导入（旧板 `S06_Argmax` 删除），S07/S08/S09 同策略；源 `.kicad_sch` 未改动 |
| 2026-11-07 | 图页可视化清理：8 页共删除 985 个电源桩线冗余 `NET` 标签（字号 196.85、值 `power_+5V`/`power_GND`）+ S15 删除 1 个根级 `_NETLABEL_` 浮空标签；同步修正 `bulktext` 源坐标 y 符号、替换导入 netflag 为原生符号。逐页重导出网表复核，3463 网络/13680 引脚/0 差异保持不变 |
