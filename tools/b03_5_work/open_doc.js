// open project + B03-5 PCB document
const prj = await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
await eda.dmt_EditorControl.openDocument('42f9160329b94bb4');
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return JSON.stringify({prj: !!prj, uuid: doc.uuid, type: doc.documentType});
