"""Player actions that share one interface for the game controller."""


class PuzzleAction:
    """Store the puzzle used by every type of player action."""

    def __init__(self, puzzle):
        self.puzzle = puzzle

    def apply(self, position):
        """Return True for a move, or False for selection/deselection."""
        raise NotImplementedError("Each action needs an apply method.")


class SelectAction(PuzzleAction):
    """Select or deselect a tile, or swap it with the selected tile."""

    def apply(self, position):
        return self.puzzle.select(position)


class RotateAction(PuzzleAction):
    """Rotate a tile clockwise, counting as one move."""

    def apply(self, position):
        self.puzzle.rotate(position)
        return True


class FlipAction(PuzzleAction):
    """Flip a tile horizontally, counting as one move."""

    def apply(self, position):
        self.puzzle.flip(position)
        return True
