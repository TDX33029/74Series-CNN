const bs = await eda.dmt_Board.getAllBoardsInfo();
return JSON.stringify(bs.map(b=>({name:(b.board&&b.board.name)||b.name, pcb:(b.pcb&&b.pcb.uuid)||null, id:b.id||b.boardId||null})));
