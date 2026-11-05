"""UCT search; each node stores reward from its previous mover's perspective."""

import math
import random
import time
from dataclasses import dataclass, field
from ai.base import SearchConfig, SearchResult, SearchStats
from ai.evaluation import rollout_value
from game.candidates import generate


@dataclass
class Node:
    player_just_moved: int
    move: int = None
    visits: int = 0
    total: float = 0.0
    untried: list = None
    children: list = field(default_factory=list)


class MCTSAgent:
    name = "MCTS"

    def choose_move(self, board, config=None, cancel=None):
        config = config or SearchConfig()
        started = time.perf_counter()
        deadline = started + config.time_limit if config.time_limit else float("inf")
        rng = random.Random(config.seed)
        stats = SearchStats(self.name, nodes=1)

        def stop():
            if cancel is not None and cancel.is_set():
                stats.cancelled = True
            if time.perf_counter() >= deadline:
                stats.timed_out = True
            return stats.cancelled or stats.timed_out

        def moves():
            return generate(board, config.radius, config.max_candidates, config.ordered, config.forcing)

        if board.terminal:
            stats.elapsed = time.perf_counter() - started
            return SearchResult(None, stats)
        root_moves = moves()
        root = Node(-board.to_move, untried=list(root_moves))
        for _ in range(config.iterations):
            if stop():
                break
            node, path, made = root, [root], 0
            interrupted = False
            try:
                # Selection: child means are rewards for the player moving here.
                while not board.terminal and not node.untried and node.children:
                    if stop():
                        interrupted = True
                        break
                    log_visits = math.log(max(1, node.visits))
                    node = max(node.children, key=lambda child: child.total / child.visits
                               + config.exploration * math.sqrt(log_visits / child.visits))
                    board.play(node.move)
                    made += 1
                    path.append(node)
                if interrupted:
                    break
                expanded = None
                parent = node
                if not board.terminal and node.untried:
                    move = rng.choice(node.untried)
                    board.play(move)
                    made += 1
                    expanded = Node(-board.to_move, move, untried=moves())
                    node = expanded
                    path.append(node)
                rollout_steps = 0
                while not board.terminal and rollout_steps < config.rollout_limit:
                    if stop():
                        interrupted = True
                        break
                    board.play(rng.choice(moves()))
                    made += 1
                    rollout_steps += 1
                    stats.rollout_moves += 1
                if interrupted or stop():
                    break
                # Attach only completed simulations, so UCT never divides by zero.
                if expanded is not None:
                    parent.untried.remove(expanded.move)
                    parent.children.append(expanded)
                    stats.nodes += 1
                if not board.terminal:
                    stats.heuristic_rollouts += 1
                for visited in path:
                    visited.visits += 1
                    visited.total += rollout_value(board, visited.player_just_moved)
                stats.iterations += 1
            finally:
                for _ in range(made):
                    board.undo()
        chosen = max(root.children, key=lambda child: (child.visits, child.total / child.visits)) if root.children else None
        if chosen:
            stats.score = chosen.total / chosen.visits
        stats.elapsed = time.perf_counter() - started
        return SearchResult(chosen.move if chosen else root_moves[0], stats,
                            {child.move: child.visits for child in root.children})

