import threading
import unittest
from dataclasses import replace

from ai.base import ALGORITHMS, SearchConfig, create_agent
from ai.evaluation import evaluate, rollout_value
from experiments.benchmark import opening_position, play_game
from game.board import Board, X, O
from tests.test_game import fingerprint, position


class SearchTests(unittest.TestCase):
    def test_forced_win_and_block_all_algorithms(self):
        fixtures = [
            ([(0, c) for c in range(4)], [(6, c) for c in (0, 2, 4, 6)], 4),
            ([(0, c) for c in (0, 2, 4, 6)], [(6, c) for c in range(4)], 46),
        ]
        for xs, os, expected in fixtures:
            for algorithm in ALGORITHMS:
                board = position(7, xs, os)
                before = fingerprint(board)
                result = create_agent(algorithm).choose_move(board, SearchConfig(time_limit=0, max_depth=2, iterations=24, rollout_limit=15))
                self.assertEqual(result.move, expected, algorithm)
                self.assertEqual(fingerprint(board), before)

    def test_alpha_beta_matches_unpruned(self):
        for size in (7, 9, 11):
            for seed in (2, 9):
                board, _ = opening_position(size, seed, 12)
                config = SearchConfig(max_depth=3, time_limit=0, max_candidates=6, iterative=False)
                before = fingerprint(board)
                plain = create_agent("Backtracking").choose_move(board, config)
                pruned = create_agent("Alpha-beta").choose_move(board, config)
                self.assertEqual(plain.stats.score, pruned.stats.score)
                self.assertEqual(plain.move, pruned.move)
                self.assertLessEqual(pruned.stats.nodes, plain.stats.nodes)
                self.assertEqual(pruned.stats.completed_depth, 3)
                self.assertEqual(fingerprint(board), before)

    def test_no_reduction_same_value(self):
        board, _ = opening_position(7, 55, 20)
        config = SearchConfig(max_depth=2, time_limit=0, radius=0, max_candidates=0, forcing=False, ordered=False, iterative=False)
        a = create_agent("Backtracking").choose_move(board, config)
        b = create_agent("Alpha-beta").choose_move(board, config)
        self.assertEqual(a.stats.score, b.stats.score)

    def test_timeout_and_cancel_restore_state(self):
        board, _ = opening_position(11, 4, 8)
        for algorithm in ALGORITHMS:
            for use_cancel in (False, True):
                before = fingerprint(board)
                cancel = threading.Event()
                if use_cancel:
                    cancel.set()
                config = SearchConfig(max_depth=15, time_limit=0.01, iterations=1_000_000, max_candidates=20)
                result = create_agent(algorithm).choose_move(board, config, cancel)
                self.assertIn(result.move, board.legal_moves())
                self.assertEqual(fingerprint(board), before)
                self.assertLess(result.stats.elapsed, 1)
                self.assertTrue(result.stats.cancelled if use_cancel else result.stats.timed_out)

    def test_mcts_fixed_iteration_reproducibility(self):
        board, _ = opening_position(7, 7, 6)
        config = SearchConfig(time_limit=0, iterations=40, rollout_limit=12, seed=123)
        a = create_agent("MCTS").choose_move(board, config)
        b = create_agent("MCTS").choose_move(board, config)
        self.assertEqual(a.move, b.move)
        self.assertEqual(a.root_visits, b.root_visits)
        self.assertEqual(sum(a.root_visits.values()), 40)
        self.assertEqual(a.stats.iterations, 40)
        self.assertEqual(a.stats.score, b.stats.score)

    def test_mcts_reward_perspective_without_tactical_filter(self):
        board = position(7, [(0, c) for c in range(4)], [(6, c) for c in (0, 2, 4, 6)])
        result = create_agent("MCTS").choose_move(board, SearchConfig(time_limit=0, iterations=300, max_candidates=3,
                                                                      forcing=False, rollout_limit=8, seed=7))
        self.assertEqual(result.move, 4)
        self.assertEqual(result.stats.score, 1.0)

    def test_mcts_reward_o_perspective(self):
        board = position(7, [(0, c) for c in (0, 2, 4, 6)] + [(2, 2)], [(6, c) for c in range(4)])
        result = create_agent("MCTS").choose_move(board, SearchConfig(time_limit=0, iterations=250, max_candidates=3,
                                                                      forcing=False, rollout_limit=8, seed=8))
        self.assertEqual(result.move, 46)
        self.assertEqual(result.stats.score, 1.0)

    def test_terminal_returns_no_move(self):
        board = position(7, [(0, c) for c in range(5)], [(6, c) for c in (0, 2, 4, 6)])
        for algorithm in ALGORITHMS:
            self.assertIsNone(create_agent(algorithm).choose_move(board).move)
        self.assertEqual(rollout_value(board, X), 1)
        self.assertEqual(rollout_value(board, O), 0)

    def test_evaluation_symmetry(self):
        board, _ = opening_position(9, 2, 14)
        self.assertEqual(evaluate(board, X), -evaluate(board, O))
        self.assertAlmostEqual(rollout_value(board, X) + rollout_value(board, O), 1)

    def test_config_validation(self):
        for settings in ({"time_limit": float("nan")}, {"time_limit": -1}, {"max_depth": 0},
                         {"iterations": 0}, {"radius": 3}, {"max_candidates": -1}, {"rollout_limit": 0}):
            with self.assertRaises(ValueError):
                SearchConfig(**settings)

    def test_complete_match_replay(self):
        config = SearchConfig(time_limit=0.005, iterations=100, max_depth=3, max_candidates=5, rollout_limit=10)
        game, moves = play_game(7, "Alpha-beta", "MCTS", 4, config, "test")
        import json
        from game.rules import symbol
        board = Board(7)
        for move in json.loads(game["opening"]):
            board.play(move)
        for record in moves:
            self.assertEqual(symbol(board.to_move), record["player"])
            board.play(record["move"])
        self.assertTrue(board.terminal)
        self.assertEqual(symbol(board.winner), game["winner"])


if __name__ == "__main__":
    unittest.main()

