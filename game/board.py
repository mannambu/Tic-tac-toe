"""Board with incremental five-cell window scores and reversible moves."""

from functools import lru_cache

EMPTY, X, O = 0, 1, -1
SIZES = (7, 9, 11)
WIN_LENGTH = 5
WIN_SCORE = 1_000_000
WEIGHTS = (0, 2, 16, 128, 4096, WIN_SCORE)
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


@lru_cache(maxsize=3)
def geometry(size):
    windows = []
    memberships = [[] for _ in range(size * size)]
    for row in range(size):
        for col in range(size):
            for dr, dc in DIRECTIONS:
                end_r, end_c = row + 4 * dr, col + 4 * dc
                if 0 <= end_r < size and 0 <= end_c < size:
                    window = tuple((row + k * dr) * size + col + k * dc for k in range(5))
                    number = len(windows)
                    windows.append(window)
                    for cell in window:
                        memberships[cell].append(number)
    return tuple(windows), tuple(tuple(items) for items in memberships)


def window_score(x_count, o_count):
    if x_count and o_count:
        return 0
    return WEIGHTS[x_count] - WEIGHTS[o_count]


class Board:
    def __init__(self, size=7):
        if size not in SIZES:
            raise ValueError(f"Board size must be one of {SIZES}.")
        self.size = size
        self.cells = [EMPTY] * (size * size)
        self.windows, self.memberships = geometry(size)
        self.x_counts = [0] * len(self.windows)
        self.o_counts = [0] * len(self.windows)
        self.score = 0
        self.to_move = X
        self.winner = EMPTY
        self.move_count = 0
        self.last_move = None
        self.history = []

    @classmethod
    def from_cells(cls, size, cells):
        board = cls(size)
        if len(cells) != size * size or any(v not in (EMPTY, X, O) for v in cells):
            raise ValueError("Invalid board cells.")
        nx, no = cells.count(X), cells.count(O)
        if nx not in (no, no + 1):
            raise ValueError("X must start and turns must alternate.")
        board.cells = list(cells)
        board.move_count = nx + no
        board.to_move = X if nx == no else O
        winners = set()
        for number, window in enumerate(board.windows):
            xc = sum(cells[i] == X for i in window)
            oc = sum(cells[i] == O for i in window)
            board.x_counts[number], board.o_counts[number] = xc, oc
            board.score += window_score(xc, oc)
            if xc == 5:
                winners.add(X)
            if oc == 5:
                winners.add(O)
        if len(winners) > 1:
            raise ValueError("Both players cannot win.")
        if winners:
            board.winner = winners.pop()
            if board.winner != -board.to_move:
                raise ValueError("Winner and turn counts disagree.")
        return board

    def copy(self):
        result = Board.from_cells(self.size, self.cells)
        result.last_move = self.last_move
        return result

    @property
    def is_draw(self):
        return not self.winner and self.move_count == self.size * self.size

    @property
    def terminal(self):
        return bool(self.winner) or self.is_draw

    def legal_moves(self):
        return [] if self.terminal else [i for i, value in enumerate(self.cells) if value == EMPTY]

    def _update(self, move, player, delta):
        counts = self.x_counts if player == X else self.o_counts
        for number in self.memberships[move]:
            self.score -= window_score(self.x_counts[number], self.o_counts[number])
            counts[number] += delta
            self.score += window_score(self.x_counts[number], self.o_counts[number])

    def play(self, move):
        if self.terminal:
            raise ValueError("The game has ended.")
        if not isinstance(move, int) or not 0 <= move < len(self.cells):
            raise ValueError("Move is outside the board.")
        if self.cells[move] != EMPTY:
            raise ValueError("Cell is already occupied.")
        self.history.append((move, self.last_move, self.winner))
        player = self.to_move
        self.cells[move] = player
        self._update(move, player, 1)
        self.move_count += 1
        self.last_move = move
        counts = self.x_counts if player == X else self.o_counts
        if any(counts[number] == WIN_LENGTH for number in self.memberships[move]):
            self.winner = player
        self.to_move = -player

    def undo(self):
        if not self.history:
            raise ValueError("No move to undo.")
        move, previous_last, previous_winner = self.history.pop()
        self.to_move = -self.to_move
        self._update(move, self.to_move, -1)
        self.cells[move] = EMPTY
        self.move_count -= 1
        self.last_move = previous_last
        self.winner = previous_winner
        return move

    def winning_moves(self, player):
        """All legal cells that would complete a five for this player."""
        if self.terminal:
            return []
        own, other = (self.x_counts, self.o_counts) if player == X else (self.o_counts, self.x_counts)
        found = set()
        for number, count in enumerate(own):
            if count == 4 and other[number] == 0:
                found.update(i for i in self.windows[number] if self.cells[i] == EMPTY)
        return sorted(found)

    def winning_line(self):
        if not self.winner:
            return []
        if self.last_move is not None:
            row, col = divmod(self.last_move, self.size)
            for dr, dc in DIRECTIONS:
                line = [self.last_move]
                for sign in (-1, 1):
                    r, c = row + sign * dr, col + sign * dc
                    while 0 <= r < self.size and 0 <= c < self.size:
                        cell = r * self.size + c
                        if self.cells[cell] != self.winner:
                            break
                        line.append(cell)
                        r, c = r + sign * dr, c + sign * dc
                if len(line) >= WIN_LENGTH:
                    return sorted(line)
        return list(next(w for w in self.windows if all(self.cells[i] == self.winner for i in w)))

