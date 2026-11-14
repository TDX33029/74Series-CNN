const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
let file = null, err = null;
try { file = await eda.sch_ManufactureData.getNetlistFile("74CNN-BRD_export", "Protel2"); } catch(e) { err = String(e); }
if (!file) { return {docType: doc ? doc.documentType : null, docName: doc ? doc.name : null, err: err || "file undefined"}; }
let text = null, err2 = null;
try { text = await file.text(); } catch(e) { err2 = String(e); }
return {docType: doc ? doc.documentType : null, docName: doc ? doc.name : null, name: file.name, size: file.size, len: text ? text.length : null, head: text ? text.slice(0, 200) : null, err: err, err2: err2};
