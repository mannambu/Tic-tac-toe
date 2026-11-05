import random
import unittest

from game.board import Board, EMPTY, O, X
from game.candidates import generate


def position(size, xs, os):
    cells = [EMPTY] * (size * size)
    for row, col in xs:
        cells[row * size + col] = X
    for row, col in os:
        if cells[row * size + col]:
            raise ValueError("Fixture overlaps.")
        cells[row * size + col] = O
    return Board.from_cells(size, cells)


def fingerprint(board):
    return (tuple(board.cells), board.to_move, board.winner, board.move_count, board.last_move,
            tuple(board.history), tuple(board.x_counts), tuple(board.o_counts), board.score)


class BoardTests(unittest.TestCase):
    def test_all_sizes_and_directions(self):
        for size in (7, 9, 11):
            lines = [([(0, c) for c in range(5)], [(size - 1, c) for c in (0, 2, 4, 6)]),
                     ([(r, 0) for r in range(5)], [(size - 1, c) for c in (1, 2, 4, 6)]),
                     ([(r, r) for r in range(5)], [(size - 1, c) for c in (0, 2, 4, 6)]),
                     ([(r, size - 1 - r) for r in range(5)], [(size - 1, c) for c in (0, 2, 4, 6)])]
            for xs, os in lines:
                with self.subTest(size=size, xs=xs):
                    board = position(size, xs[:4], os)
                    before = fingerprint(board)
                    board.play(xs[4][0] * size + xs[4][1])
                    self.assertEqual(board.winner, X)
                    self.assertEqual(len(board.winning_line()), 5)
                    self.assertTrue(board.terminal)
                    self.assertEqual(board.legal_moves(), [])
                    with self.assertRaises(ValueError):
                        board.play(size * size - 1)
                    board.undo()
                    self.assertEqual(fingerprint(board), before)

    def test_six_and_blocked_ends_win(self):
        board = position(9, [(4, c) for c in (1, 2, 3, 5, 6)],
                         [(4, 0), (4, 7), (0, 0), (0, 2), (0, 4)])
        board.play(4 * 9 + 4)
        self.assertEqual(board.winner, X)
        self.assertEqual(len(board.winning_line()), 6)

    def test_o_can_win(self):
        board = position(7, [(0, c) for c in (0, 2, 4, 6)] + [(2, 2)], [(6, c) for c in range(4)])
        board.play(6 * 7 + 4)
        self.assertEqual(board.winner, O)

    def test_illegal_moves(self):
        board = Board()
        for move in (-1, 49, "0", None):
            with self.assertRaises(ValueError):
                board.play(move)
        board.play(0)
        with self.assertRaises(ValueError):
            board.play(0)
        board.undo()
        with self.assertRaises(ValueError):
            board.undo()
        with self.assertRaises(ValueError):
            Board(3)

    def test_random_incremental_state_and_undo(self):
        rng = random.Random(9)
        for size in (7, 9, 11):
            board = Board(size)
            before = fingerprint(board)
            for _ in range(35):
                board.play(rng.choice(board.legal_moves()))
                rebuilt = Board.from_cells(size, board.cells)
                self.assertEqual(board.score, rebuilt.score)
                self.assertEqual(board.x_counts, rebuilt.x_counts)
                self.assertEqual(board.o_counts, rebuilt.o_counts)
                self.assertEqual(board.winner, rebuilt.winner)
                if board.terminal:
                    break
            while board.history:
                board.undo()
            self.assertEqual(fingerprint(board), before)

    def test_full_board_draw(self):
        # This period-4 coloring avoids five along every direction.
        size = 7
        cells = [X if (r + 2 * c) % 4 < 2 else O for r in range(size) for c in range(size)]
        # Its counts are 25 X / 24 O, so it is a legal terminal draw position.
        board = Board.from_cells(size, cells)
        self.assertTrue(board.is_draw)
        self.assertTrue(board.terminal)
        self.assertEqual(board.winning_line(), [])

    def test_invalid_snapshot(self):
        with self.assertRaises(ValueError):
            Board.from_cells(7, [O] + [0] * 48)
        with self.assertRaises(ValueError):
            Board.from_cells(7, [0] * 48)


class CandidateTests(unittest.TestCase):
    def test_empty_board_and_full_mode(self):
        for size in (7, 9, 11):
            board = Board(size)
            self.assertEqual(generate(board), [size * size // 2])
            self.assertEqual(len(generate(board, radius=0, max_candidates=0)), size * size)

    def test_urgent_moves_survive_cap(self):
        board = position(7, [(3, c) for c in range(1, 5)], [(0, c) for c in (0, 2, 4, 6)])
        self.assertEqual(set(generate(board, max_candidates=1)), {21, 26})

    def test_block_and_gap(self):
        board = position(7, [(0, c) for c in (0, 2, 4, 6)], [(3, c) for c in (0, 1, 3, 4)])
        self.assertEqual(generate(board), [23])

    def test_win_before_block(self):
        board = position(7, [(1, c) for c in range(4)], [(3, c) for c in range(4)])
        self.assertEqual(generate(board), [11])


if __name__ == "__main__":
    unittest.main()

