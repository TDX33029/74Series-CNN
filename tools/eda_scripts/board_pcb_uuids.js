const bs = await eda.dmt_Board.getAllBoardsInfo();
const out = [];
for (const b of bs) {
  const name = (b.board && b.board.name) || b.name;
  let pcb = null;
  try { const bi = await eda.dmt_Board.getBoardInfo(name); pcb = bi && bi.pcb && bi.pcb.uuid; } catch(e) {}
  out.push({name, pcb});
}
return JSON.stringify(out);
