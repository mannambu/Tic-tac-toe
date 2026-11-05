"""Negamax via reversible backtracking, optionally with alpha-beta bounds."""

import time
from ai.base import SearchConfig, SearchResult, SearchStats
from ai.evaluation import evaluate
from game.board import WIN_SCORE
from game.candidates import generate


class SearchInterrupted(Exception):
    pass


class MinimaxAgent:
    pruning = False
    name = "Backtracking"

    def choose_move(self, board, config=None, cancel=None):
        config = config or SearchConfig()
        started = time.perf_counter()
        deadline = started + config.time_limit if config.time_limit else float("inf")
        stats = SearchStats(self.name)

        def check():
            if cancel is not None and cancel.is_set():
                stats.cancelled = True
                raise SearchInterrupted
            if time.perf_counter() >= deadline:
                stats.timed_out = True
                raise SearchInterrupted

        def moves():
            return generate(board, config.radius, config.max_candidates, config.ordered, config.forcing)

        def search(depth, alpha, beta, ply):
            check()
            stats.nodes += 1
            if board.winner:
                return -WIN_SCORE + ply
            if board.is_draw:
                return 0
            if depth == 0:
                return evaluate(board, board.to_move)
            best = -float("inf")
            for move in moves():
                check()
                board.play(move)
                try:
                    value = -search(depth - 1, -beta, -alpha, ply + 1)
                finally:
                    board.undo()
                best = max(best, value)
                if self.pruning:
                    alpha = max(alpha, best)
                    if alpha >= beta:
                        stats.cutoffs += 1
                        break
            return best

        if board.terminal:
            stats.elapsed = time.perf_counter() - started
            return SearchResult(None, stats)
        root_moves = moves()
        # A legal fallback is available even when the first iteration cannot finish.
        selected = root_moves[0]
        depths = range(1, config.max_depth + 1) if config.iterative else (config.max_depth,)
        try:
            for depth in depths:
                check()
                stats.nodes += 1
                best_value, best_move = -float("inf"), root_moves[0]
                alpha, beta = -float("inf"), float("inf")
                for move in root_moves:
                    check()
                    board.play(move)
                    try:
                        value = -search(depth - 1, -beta, -alpha, 1)
                    finally:
                        board.undo()
                    if value > best_value:
                        best_value, best_move = value, move
                    if self.pruning:
                        alpha = max(alpha, best_value)
                selected = best_move
                stats.completed_depth = depth
                stats.score = best_value
                if abs(best_value) >= WIN_SCORE - len(board.cells):
                    break
        except SearchInterrupted:
            pass
        stats.elapsed = time.perf_counter() - started
        return SearchResult(selected, stats)

