"""Shared, explicit search-space reduction and deterministic move ordering."""

from functools import lru_cache
from game.board import EMPTY, WEIGHTS, X


@lru_cache(maxsize=12)
def neighborhoods(size, radius):
    return tuple(
        tuple(r * size + c
              for r in range(max(0, row - radius), min(size, row + radius + 1))
              for c in range(max(0, col - radius), min(size, col + radius + 1)))
        for row in range(size) for col in range(size)
    )


def priority(board, move, player):
    own, other = (board.x_counts, board.o_counts) if player == X else (board.o_counts, board.x_counts)
    value = 0
    for number in board.memberships[move]:
        a, b = own[number], other[number]
        if b == 0:
            value += 2 * (WEIGHTS[a + 1] - WEIGHTS[a])
        if a == 0:
            value += WEIGHTS[b + 1] - WEIGHTS[b]
    row, col = divmod(move, board.size)
    center = board.size // 2
    return value, -abs(row - center) - abs(col - center), -move


def generate(board, radius=2, max_candidates=12, ordered=True, forcing=True):
    if board.terminal:
        return []
    if forcing:
        urgent = board.winning_moves(board.to_move) or board.winning_moves(-board.to_move)
        if urgent:
            # Never drop an immediate winning/blocking cell due to the candidate cap.
            return sorted(urgent, key=lambda m: priority(board, m, board.to_move), reverse=True) if ordered else urgent
    if board.move_count == 0 and radius > 0:
        return [(board.size * board.size) // 2]
    if radius == 0:
        moves = board.legal_moves()
    else:
        nearby = neighborhoods(board.size, radius)
        possible = set()
        for cell, value in enumerate(board.cells):
            if value:
                possible.update(nearby[cell])
        moves = sorted(i for i in possible if board.cells[i] == EMPTY)
    # Rank before limiting even when traversal ordering is disabled.
    if ordered or (max_candidates and len(moves) > max_candidates):
        moves.sort(key=lambda m: priority(board, m, board.to_move), reverse=True)
    if max_candidates:
        moves = moves[:max_candidates]
    return moves if ordered else sorted(moves)

