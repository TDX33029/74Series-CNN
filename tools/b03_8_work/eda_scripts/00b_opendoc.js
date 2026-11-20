await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
await eda.dmt_EditorControl.openDocument('c03b63553aa7180b');
await new Promise(r=>setTimeout(r,2000));
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
return JSON.stringify({uuid:doc.uuid,type:doc.documentType});
