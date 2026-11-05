"""An incremental, symmetric heuristic shared by both Minimax searches."""

import math
from game.board import WIN_SCORE


def evaluate(board, player):
    # A heuristic must never outweigh a proven win, even on the largest board.
    return max(-WIN_SCORE // 2, min(WIN_SCORE // 2, board.score * player))


def rollout_value(board, player):
    if board.winner:
        return 1.0 if board.winner == player else 0.0
    if board.is_draw:
        return 0.5
    # Explicit approximate value for truncated simulations, bounded to [0, 1].
    return 0.5 + 0.5 * math.tanh(evaluate(board, player) / 8192.0)

