"""Public rule helpers; five or more wins, even with both ends blocked."""

from game.board import EMPTY, O, X


def symbol(player):
    return {X: "X", O: "O", EMPTY: "Draw"}[player]


def result_text(board):
    if board.winner:
        return f"{symbol(board.winner)} wins"
    if board.is_draw:
        return "Draw"
    return f"{symbol(board.to_move)} to move"

