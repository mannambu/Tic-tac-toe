"""Run fixed-depth comparisons and paired, equal-time AI matches.

Examples:
    python -m experiments.benchmark --output results/quick --time 0.04
    python -m experiments.benchmark --mode compare --depths 2 3 4
"""

import argparse
import csv
import itertools
import json
import platform
import random
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from ai.base import ALGORITHMS, SearchConfig, create_agent
from game.board import Board, X
from game.candidates import generate
from game.rules import symbol


def write_csv(path, rows):
    if rows:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def opening_position(size, seed, plies):
    """Shared legal opening, generated independently of the tested agents."""
    rng = random.Random(seed)
    board = Board(size)
    sequence = []
    for _ in range(plies):
        options = generate(board, max_candidates=0, forcing=False)
        rng.shuffle(options)
        chosen = None
        for move in options:
            board.play(move)
            terminal = board.terminal
            board.undo()
            if not terminal:
                chosen = move
                break
        if chosen is None:
            break
        board.play(chosen)
        sequence.append(chosen)
    return board, sequence


def compare_depths(sizes, depths, seeds, config):
    rows = []
    for size, seed, depth in itertools.product(sizes, seeds, depths):
        board, sequence = opening_position(size, seed, 10)
        settings = replace(config, max_depth=depth, time_limit=0, iterative=False, seed=seed)
        agents = ("Backtracking", "Alpha-beta") if seed % 2 else ("Alpha-beta", "Backtracking")
        results = {}
        for algorithm in agents:
            result = create_agent(algorithm).choose_move(board, settings)
            results[algorithm] = result
            if result.stats.completed_depth != depth:
                raise AssertionError("Fixed-depth experiment did not complete.")
            rows.append({"size": size, "seed": seed, "depth": depth, "algorithm": algorithm,
                         "move": result.move, "score": result.stats.score, "nodes": result.stats.nodes,
                         "cutoffs": result.stats.cutoffs, "seconds": result.stats.elapsed,
                         "max_candidates": config.max_candidates, "radius": config.radius,
                         "ordered": config.ordered, "forcing": config.forcing,
                         "opening": json.dumps(sequence)})
        if results["Backtracking"].stats.score != results["Alpha-beta"].stats.score:
            raise AssertionError(f"Minimax values differ: size={size}, seed={seed}, depth={depth}")
        print(f"Depth comparison: {size}x{size}, seed={seed}, depth={depth}: values match", flush=True)
    return rows


def play_game(size, x_agent, o_agent, seed, config, game_id, opening_plies=4):
    board, opening = opening_position(size, seed, opening_plies)
    agents = {X: create_agent(x_agent), -X: create_agent(o_agent)}
    names = {X: x_agent, -X: o_agent}
    records = []
    started = time.perf_counter()
    while not board.terminal:
        player = board.to_move
        settings = replace(config, seed=seed * 1000 + board.move_count)
        snapshot = tuple(board.cells), board.to_move, board.score, len(board.history)
        result = agents[player].choose_move(board, settings)
        if snapshot != (tuple(board.cells), board.to_move, board.score, len(board.history)):
            raise AssertionError("Search changed the game board.")
        if result.move not in board.legal_moves():
            raise AssertionError(f"Illegal move from {names[player]}: {result.move}")
        row, col = divmod(result.move, size)
        records.append({"game_id": game_id, "size": size, "seed": seed, "ply": board.move_count + 1,
                        "player": symbol(player), "algorithm": names[player], "row": row + 1, "col": col + 1,
                        "move": result.move, **asdict(result.stats)})
        board.play(result.move)
    game = {"game_id": game_id, "size": size, "seed": seed, "x_agent": x_agent, "o_agent": o_agent,
            "winner": symbol(board.winner), "winner_agent": names[board.winner] if board.winner else "Draw",
            "plies": board.move_count, "seconds": time.perf_counter() - started,
            "opening": json.dumps(opening)}
    return game, records


def run_matches(sizes, seeds, config):
    games, moves = [], []
    for size, pair, seed in itertools.product(sizes, itertools.combinations(ALGORITHMS, 2), seeds):
        for x_agent, o_agent in (pair, pair[::-1]):
            game_id = f"g{len(games) + 1:03d}"
            game, records = play_game(size, x_agent, o_agent, seed, config, game_id)
            games.append(game)
            moves.extend(records)
            print(f"{game_id}: {size}x{size} {x_agent} (X) vs {o_agent} (O): "
                  f"{game['winner_agent']} / {game['winner']} in {game['plies']} plies", flush=True)
    return games, moves


def summarize(games, moves):
    groups = defaultdict(lambda: {"games": 0, "wins": 0, "draws": 0, "losses": 0, "times": [], "depths": [], "iterations": []})
    for game in games:
        for side in ("x_agent", "o_agent"):
            algorithm = game[side]
            row = groups[(game["size"], algorithm)]
            row["games"] += 1
            row["draws" if game["winner_agent"] == "Draw" else "wins" if game["winner_agent"] == algorithm else "losses"] += 1
    for move in moves:
        row = groups[(move["size"], move["algorithm"])]
        row["times"].append(move["elapsed"])
        if move["algorithm"] != "MCTS":
            row["depths"].append(move["completed_depth"])
        else:
            row["iterations"].append(move["iterations"])
    return [{"size": size, "algorithm": algorithm, "games": row["games"], "wins": row["wins"],
             "draws": row["draws"], "losses": row["losses"], "win_rate": row["wins"] / row["games"],
             "score_rate": (row["wins"] + 0.5 * row["draws"]) / row["games"],
             "mean_move_seconds": statistics.mean(row["times"]) if row["times"] else 0,
             "max_move_seconds": max(row["times"], default=0),
             "mean_completed_depth": statistics.mean(row["depths"]) if row["depths"] else "",
             "mean_mcts_iterations": statistics.mean(row["iterations"]) if row["iterations"] else ""}
            for (size, algorithm), row in sorted(groups.items())]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("all", "compare", "matches"), default="all")
    parser.add_argument("--output", type=Path, default=Path("results/quick"))
    parser.add_argument("--sizes", type=int, nargs="+", choices=(7, 9, 11), default=[7, 9, 11])
    parser.add_argument("--depths", type=int, nargs="+", default=[2, 3])
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 28])
    parser.add_argument("--time", type=float, default=0.04, help="Seconds per AI move (matches only, > 0).")
    parser.add_argument("--cap", type=int, default=8, help="Candidate cap; 0 = unlimited.")
    parser.add_argument("--radius", type=int, choices=(0, 1, 2), default=2, help="0 = all empty cells.")
    parser.add_argument("--match-depth", type=int, default=20, help="High ceiling; time is the practical limit.")
    parser.add_argument("--iterations", type=int, default=1_000_000)
    parser.add_argument("--rollout-limit", type=int, default=60)
    parser.add_argument("--unordered", action="store_true")
    parser.add_argument("--no-forcing", action="store_true", help="Disable immediate win/block filtering.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = SearchConfig(max_depth=args.match_depth, time_limit=args.time, max_candidates=args.cap,
                              radius=args.radius, iterations=args.iterations, rollout_limit=args.rollout_limit,
                              ordered=not args.unordered, forcing=not args.no_forcing)
        if args.time <= 0 or any(depth < 1 for depth in args.depths):
            raise ValueError("Match time and depths must be positive.")
    except ValueError as exc:
        parser.error(str(exc))
    files = ("metadata.json", "depth_comparison.csv", "games.csv", "moves.csv", "summary.csv")
    if not args.overwrite and any((args.output / name).exists() for name in files):
        parser.error("Output already contains results. Choose another --output or use --overwrite.")
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = {"created_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                "platform": platform.platform(), "processor": platform.processor(),
                "config": asdict(config), "sizes": args.sizes, "depths": args.depths, "seeds": args.seeds,
                "mode": args.mode, "status": "running", "completed_files": [],
                "rules": "X starts; >=5 consecutive wins; blocked ends allowed; no forbidden moves",
                "method": "Paired colors and identical 4-ply openings per size/seed. Soft wall-clock search budget; process startup excluded.",
                "limitations": "Candidate filtering and caps are approximate. MCTS cutoffs use heuristic values. Few seeds and short budgets do not establish a reliable strength ranking."}
    metadata_path = args.output / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        if args.mode in ("all", "compare"):
            rows = compare_depths(args.sizes, args.depths, args.seeds, config)
            write_csv(args.output / "depth_comparison.csv", rows)
            metadata["completed_files"].append("depth_comparison.csv")
        if args.mode in ("all", "matches"):
            games, moves = run_matches(args.sizes, args.seeds, config)
            write_csv(args.output / "games.csv", games)
            write_csv(args.output / "moves.csv", moves)
            write_csv(args.output / "summary.csv", summarize(games, moves))
            metadata["completed_files"].extend(["games.csv", "moves.csv", "summary.csv"])
        metadata["status"] = "complete"
    except BaseException:
        metadata["status"] = "interrupted_or_failed"
        raise
    finally:
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results saved to {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()

