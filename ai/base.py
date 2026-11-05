from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SearchConfig:
    max_depth: int = 3
    time_limit: float = 1.0
    iterations: int = 1500
    radius: int = 2
    max_candidates: int = 12
    ordered: bool = True
    forcing: bool = True
    iterative: bool = True
    rollout_limit: int = 60
    exploration: float = 1.4142135623730951
    seed: int = 0

    def __post_init__(self):
        import math
        if self.max_depth < 1 or self.iterations < 1 or self.rollout_limit < 1:
            raise ValueError("Depth, iterations and rollout limit must be positive.")
        if not math.isfinite(self.time_limit) or self.time_limit < 0:
            raise ValueError("Time limit must be finite and nonnegative (0 = unlimited).")
        if self.radius not in (0, 1, 2) or self.max_candidates < 0:
            raise ValueError("Radius must be 0, 1 or 2; candidate cap must be nonnegative.")
        if not math.isfinite(self.exploration) or self.exploration < 0:
            raise ValueError("Exploration must be finite and nonnegative.")


@dataclass
class SearchStats:
    algorithm: str
    elapsed: float = 0.0
    nodes: int = 0
    cutoffs: int = 0
    completed_depth: int = 0
    iterations: int = 0
    rollout_moves: int = 0
    heuristic_rollouts: int = 0
    timed_out: bool = False
    cancelled: bool = False
    score: Optional[float] = None


@dataclass
class SearchResult:
    move: Optional[int]
    stats: SearchStats
    root_visits: dict = field(default_factory=dict)


def create_agent(name):
    if name == "Backtracking":
        from ai.backtracking import BacktrackingAgent
        return BacktrackingAgent()
    if name == "Alpha-beta":
        from ai.alphabeta import AlphaBetaAgent
        return AlphaBetaAgent()
    if name == "MCTS":
        from ai.mcts import MCTSAgent
        return MCTSAgent()
    raise ValueError(f"Unknown algorithm: {name}")


ALGORITHMS = ("Backtracking", "Alpha-beta", "MCTS")

