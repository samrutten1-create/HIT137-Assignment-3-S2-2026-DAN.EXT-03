"""Coordinate puzzle actions, scoring, hints, and completion."""

import math
import random
import time
import tkinter as tk
from tkinter import messagebox

from puzzle.actions import FlipAction, RotateAction, SelectAction
from puzzle.puzzle import Puzzle


class GameManager:
    """Manage one image's round using the existing puzzle and GUI objects."""

    MAX_HINTS = 3

    def __init__(self, gui, time_limit=0):
        self.gui = gui
        self.processor = gui.image_processor
        self.puzzle = Puzzle(self.processor)
        self.select_action = SelectAction(self.puzzle)
        self.rotate_action = RotateAction(self.puzzle)
        self.flip_action = FlipAction(self.puzzle)
        self.moves = 0
        self.hints_used = 0
        self.hint_tile = None
        self.finished = False
        self.timed_out = False
        self.deadline = None
        self.timer_after_id = None

        if self.processor.tiles and self.processor.incorrect_tile_count == 0:
            self.finished = True

        # A new manager is created on every successful image load.
        self.gui.hint_button.config(command=self.show_hint)
        self.gui.solve_button.config(command=self.solve_puzzle)
        self._clear_hint()
        self._draw_selection()
        self.mark_correct()
        self.update_score()
        self._update_buttons()
        self.gui.timer_label.config(text="Time: Off")
        if time_limit > 0 and self.processor.tiles and not self.finished:
            # A deadline prevents a delayed callback from slowing the countdown.
            self.deadline = time.monotonic() + time_limit
            self._update_timer()

    def stop_timer(self):
        """Cancel a pending countdown when solving, reloading, or closing."""
        if self.timer_after_id is not None:
            self.gui.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None

    def _update_timer(self):
        """Update the countdown once a second without blocking the GUI."""
        self.timer_after_id = None
        if self.finished or self.deadline is None:
            return
        remaining = max(0, math.ceil(self.deadline - time.monotonic()))
        minutes, seconds = divmod(remaining, 60)
        self.gui.timer_label.config(text=f"Time: {minutes}:{seconds:02d}")
        if not self._time_expired():
            self.timer_after_id = self.gui.root.after(1000, self._update_timer)

    def _time_expired(self):
        """Check the deadline before accepting a click or hint, too."""
        if self.finished or self.deadline is None:
            return self.timed_out
        if time.monotonic() < self.deadline:
            return False

        self.finished = True
        self.timed_out = True
        self.stop_timer()
        self.gui.timer_label.config(text="Time: 0:00 (expired)")
        self.puzzle.selected_position = None
        self._clear_hint()
        self._draw_selection()
        self._update_buttons()
        messagebox.showinfo(
            "Time Is Up",
            "The time limit has ended. Load another image to try again, "
            "or use Solve to view the restored picture.",
            parent=self.gui.root,
        )
        return True

    def left_click(self, event):
        """Select, deselect, or swap tiles. Only a swap counts as a move."""
        return self._handle_action(self.select_action, event)

    def right_click(self, event):
        """Rotate the clicked tile 90 degrees clockwise."""
        return self._handle_action(self.rotate_action, event)

    def shift_left_click(self, event):
        """Flip the clicked tile horizontally without selecting it."""
        return self._handle_action(self.flip_action, event)

    def _handle_action(self, action, event):
        """Use the same apply method for each action type (polymorphism)."""
        position = self._get_position(event)
        if position is not None:
            if action.apply(position):
                self._record_move()
            else:
                self._draw_selection()
        return "break"

    def show_hint(self):
        """Mark one incorrect tile and its home, using one of three hints."""
        if self.finished or self._time_expired() or self.hints_used >= self.MAX_HINTS:
            return

        incorrect_tiles = []
        for tile in self.processor.tiles:
            if not tile.is_correct:
                incorrect_tiles.append(tile)

        if not incorrect_tiles:
            return

        self.hint_tile = random.choice(incorrect_tiles)
        self.hints_used += 1
        self._draw_hint()
        self._update_buttons()

    def solve_puzzle(self):
        """Restore the original board, clear the score, and end the round."""
        if (self.finished and not self.timed_out) or self.processor.original_image is None:
            return

        self.processor.solved_image()
        self.stop_timer()
        self.moves = 0
        self.puzzle.selected_position = None
        self.finished = True
        self.timed_out = False
        self._clear_hint()
        self._redraw_board()
        messagebox.showinfo(
            "Puzzle Solved",
            "The original image has been restored.",
            parent=self.gui.root,
        )

    def update_score(self):
        """Display the moves made and tiles still in the wrong state."""
        incorrect = self.processor.incorrect_tile_count
        self.gui.score_label.config(
            text=f"Moves: {self.moves} | Incorrect: {incorrect}"
        )

    def _record_move(self):
        """Refresh the round after a successful swap, rotation, or flip."""
        self.moves += 1
        self._clear_hint()
        self._redraw_board()
        self._check_completion()

    def _check_completion(self):
        """Notify the player once and lock a board they have restored."""
        if self.finished or not self.processor.tiles:
            return
        if self.processor.incorrect_tile_count != 0:
            return

        self.finished = True
        self.stop_timer()
        self.puzzle.selected_position = None
        self._clear_hint()
        self._draw_selection()
        self._update_buttons()
        messagebox.showinfo(
            "Puzzle Complete",
            f"You restored the picture!\nMoves used: {self.moves}",
            parent=self.gui.root,
        )

    def _update_buttons(self):
        hint_state = tk.DISABLED
        solve_state = tk.DISABLED
        if self.processor.tiles and not self.finished:
            solve_state = tk.NORMAL
            if self.hints_used < self.MAX_HINTS:
                hint_state = tk.NORMAL
        elif self.processor.tiles and self.timed_out:
            solve_state = tk.NORMAL

        remaining = self.MAX_HINTS - self.hints_used
        self.gui.hint_button.config(text=f"Hint ({remaining})", state=hint_state)
        self.gui.solve_button.config(state=solve_state)

    def _image_bounds(self, canvas, image):
        """Match the centred image placement used by the GUI."""
        height, width = image.shape[:2]
        left = (int(canvas.cget("width")) - width) // 2
        top = (int(canvas.cget("height")) - height) // 2
        return left, top, width, height

    def _get_position(self, event):
        """Convert a canvas click to a tile, ignoring margins and locked rounds."""
        if self.finished or self._time_expired() or not self.processor.tiles:
            return None
        if self.processor.transformed_image is None:
            return None

        left, top, width, height = self._image_bounds(
            self.gui.canvas_game, self.processor.transformed_image
        )
        x = event.x - left
        y = event.y - top
        if x < 0 or y < 0 or x >= width or y >= height:
            return None

        tile_width = width // self.puzzle.grid_size
        tile_height = height // self.puzzle.grid_size
        return y // tile_height, x // tile_width

    def _redraw_board(self):
        """Display the latest tile images, grid, and overlays."""
        if not self.processor.tiles:
            return

        self.processor.transformed_image = self.processor.reassemble_image()
        image = self.processor.transformed_image
        self.gui.game_photo = self.gui.display_image(self.gui.canvas_game, image)
        self.gui.draw_game_grid(image)
        self.mark_correct()
        self._draw_selection()
        self._draw_hint()
        self.update_score()
        self._update_buttons()

    def mark_correct(self):
        """Draw a green tick only for tiles with correct position and orientation."""
        self.gui.canvas_game.delete("tick")
        if self.processor.transformed_image is None or not self.processor.tiles:
            return

        left, top, width, height = self._image_bounds(
            self.gui.canvas_game, self.processor.transformed_image
        )
        tile_width = width // self.puzzle.grid_size
        tile_height = height // self.puzzle.grid_size
        for tile in self.processor.tiles:
            if tile.is_correct:
                row, column = tile.current_position
                x = left + column * tile_width + min(14, tile_width // 2)
                y = top + row * tile_height + min(14, tile_height // 2)
                self.gui.canvas_game.create_text(
                    x, y, text="\u2714", fill="#00aa00",
                    font=("Arial", 12, "bold"), tags="tick",
                )

    def _draw_selection(self):
        self.gui.canvas_game.delete("selection")
        if self.puzzle.selected_position is None:
            return

        left, top, width, height = self._image_bounds(
            self.gui.canvas_game, self.processor.transformed_image
        )
        tile_width = width // self.puzzle.grid_size
        tile_height = height // self.puzzle.grid_size
        row, column = self.puzzle.selected_position
        x = left + column * tile_width
        y = top + row * tile_height
        self.gui.canvas_game.create_rectangle(
            x, y, x + tile_width, y + tile_height,
            outline="#ff9900", width=3, tags="selection",
        )

    def _clear_hint(self):
        self.hint_tile = None
        self._draw_hint()

    def _draw_hint(self):
        self.gui.canvas_game.delete("hint")
        self.gui.canvas_orig.delete("hint")
        if self.hint_tile is None:
            return

        self._draw_hint_circle(
            self.gui.canvas_game, self.processor.transformed_image,
            self.hint_tile.current_position,
        )
        self._draw_hint_circle(
            self.gui.canvas_orig, self.processor.original_image,
            self.hint_tile.home_position,
        )

    def _draw_hint_circle(self, canvas, image, position):
        left, top, width, height = self._image_bounds(canvas, image)
        tile_width = width // self.puzzle.grid_size
        tile_height = height // self.puzzle.grid_size
        row, column = position
        x = left + column * tile_width + tile_width // 2
        y = top + row * tile_height + tile_height // 2
        radius = min(tile_width, tile_height) // 4
        canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            outline="blue", width=3, tags="hint",
        )
