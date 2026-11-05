"""Replay saved games and validate experiment CSVs against the game engine."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from game.board import Board
from game.rules import symbol


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def verify(directory):
    directory = Path(directory)
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "complete", "Run did not finish."
    checked_pairs, checked_games, checked_moves = 0, 0, 0
    files = metadata["completed_files"]
    if "depth_comparison.csv" in files:
        pairs = defaultdict(dict)
        for row in read_csv(directory / "depth_comparison.csv"):
            pairs[(row["size"], row["seed"], row["depth"])][row["algorithm"]] = row
        for pair in pairs.values():
            a, b = pair["Backtracking"], pair["Alpha-beta"]
            assert a["score"] == b["score"], "Minimax values differ."
            assert int(b["nodes"]) <= int(a["nodes"]), "Pruning visited more nodes."
            assert a["opening"] == b["opening"], "Inputs differ."
            checked_pairs += 1
    if "games.csv" in files:
        moves = defaultdict(list)
        for row in read_csv(directory / "moves.csv"):
            moves[row["game_id"]].append(row)
        games = read_csv(directory / "games.csv")
        assert len({g["game_id"] for g in games}) == len(games), "Duplicate game IDs."
        counts = defaultdict(lambda: {"games": 0, "wins": 0, "draws": 0, "losses": 0})
        for game in games:
            board = Board(int(game["size"]))
            for move in json.loads(game["opening"]):
                board.play(move)
            for row in moves.pop(game["game_id"], []):
                move = int(row["move"])
                assert row["player"] == symbol(board.to_move), "Turn mismatch."
                assert int(row["ply"]) == board.move_count + 1, "Ply mismatch."
                assert row["algorithm"] == game["x_agent" if board.to_move == 1 else "o_agent"]
                assert int(row["row"]) == move // board.size + 1 and int(row["col"]) == move % board.size + 1
                assert float(row["elapsed"]) >= 0
                board.play(move)
                checked_moves += 1
            assert board.terminal, "Game unfinished."
            assert symbol(board.winner) == game["winner"], "Winner mismatch."
            assert board.move_count == int(game["plies"]), "Move count mismatch."
            winner_agent = "Draw" if not board.winner else game["x_agent" if board.winner == 1 else "o_agent"]
            assert winner_agent == game["winner_agent"]
            for name in (game["x_agent"], game["o_agent"]):
                row = counts[(game["size"], name)]
                row["games"] += 1
                row["draws" if winner_agent == "Draw" else "wins" if winner_agent == name else "losses"] += 1
            checked_games += 1
        assert not moves, "Moves reference unknown games."
        summaries = read_csv(directory / "summary.csv")
        assert len(summaries) == len(counts)
        for summary in summaries:
            expected = counts[(summary["size"], summary["algorithm"])]
            assert all(int(summary[k]) == value for k, value in expected.items()), "Summary totals differ."
    return {"depth_pairs": checked_pairs, "games_replayed": checked_games, "ai_moves_replayed": checked_moves}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory), indent=2))

