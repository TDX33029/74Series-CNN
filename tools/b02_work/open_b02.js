const proj = await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
const boards = await eda.dmt_Board.getAllBoardsInfo();
const b02 = boards.find(b => b.name && b.name.includes('B02'));
await eda.dmt_EditorControl.openDocument('a8a7bb9eb952a5f7');
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return JSON.stringify({docType: doc.documentType, uuid: doc.uuid, b02board: b02 ? {name: b02.name, pcb: b02.pcb} : null, nBoards: boards.length});
