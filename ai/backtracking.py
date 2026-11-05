from ai.minimax import MinimaxAgent


class BacktrackingAgent(MinimaxAgent):
    """Depth-limited Minimax using backtracking, without pruning."""
    name = "Backtracking"
    pruning = False

