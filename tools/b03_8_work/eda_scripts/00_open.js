await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
const boards=await eda.dmt_Board.getAllBoardsInfo();
const b8=boards.find(b=>b.name==='B03-8_MEMORY'||(b.board&&b.board.name==='B03-8_MEMORY'));
return JSON.stringify({n:boards.length,boards:boards.map(x=>({name:x.name,pcb:x.pcb&&x.pcb.uuid}))});
