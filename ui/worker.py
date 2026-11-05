"""Spawn-safe AI worker: no Tk objects ever cross a process boundary."""

import traceback
from dataclasses import asdict
from ai.base import SearchConfig, create_agent
from game.board import Board


def search_worker(output, cancel, request_id, size, cells, algorithm, settings):
    try:
        board = Board.from_cells(size, cells)
        result = create_agent(algorithm).choose_move(board, SearchConfig(**settings), cancel)
        output.put({"ok": True, "request_id": request_id, "move": result.move,
                    "stats": asdict(result.stats)})
    except Exception:
        output.put({"ok": False, "request_id": request_id, "error": traceback.format_exc()})

