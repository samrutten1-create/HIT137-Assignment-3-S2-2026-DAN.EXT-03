"""Check puzzle actions and their effect on game scoring and hints."""

import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from game.game_manager import GameManager
from gui.main_window import PuzzleGUI
from image_processing.image_processor import ImageProcessor
from puzzle.actions import FlipAction, PuzzleAction, RotateAction, SelectAction
from puzzle.puzzle import Puzzle


def make_processor(grid_size):
    """Create a small board with distinct pixels, without reading image files."""
    side = grid_size * 4
    image = np.arange(side * side * 3).reshape(side, side, 3).astype(np.uint8)
    processor = ImageProcessor()
    processor.grid_size = grid_size
    processor.original_image = image.copy()
    processor.tiles = processor.slice_image(image, grid_size)
    processor.transformed_image = processor.reassemble_image()
    return processor


class PuzzleActionTests(unittest.TestCase):
    def test_base_action_requires_an_override(self):
        puzzle = Puzzle(make_processor(3))
        action = PuzzleAction(puzzle)
        self.assertIs(action.puzzle, puzzle)
        with self.assertRaises(NotImplementedError):
            action.apply((0, 0))

    def test_selection_deselection_and_swap(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                puzzle = Puzzle(make_processor(grid_size))
                action = SelectAction(puzzle)
                self.assertIsInstance(action, PuzzleAction)
                self.assertIs(action.puzzle, puzzle)
                first_tile = puzzle.get_tile_at((0, 0))
                second_tile = puzzle.get_tile_at((0, 1))
                first_image = first_tile.image.copy()
                second_image = second_tile.image.copy()

                self.assertFalse(action.apply((0, 0)))
                self.assertEqual(puzzle.selected_position, (0, 0))
                self.assertFalse(action.apply((0, 0)))
                self.assertIsNone(puzzle.selected_position)
                self.assertIs(puzzle.get_tile_at((0, 0)), first_tile)

                self.assertFalse(action.apply((0, 0)))
                self.assertTrue(action.apply((0, 1)))
                self.assertIsNone(puzzle.selected_position)
                self.assertIs(puzzle.get_tile_at((0, 0)), second_tile)
                self.assertIs(puzzle.get_tile_at((0, 1)), first_tile)
                self.assertEqual(first_tile.current_position, (0, 1))
                self.assertEqual(second_tile.current_position, (0, 0))
                self.assertEqual(first_tile.home_position, (0, 0))
                self.assertEqual(second_tile.home_position, (0, 1))
                np.testing.assert_array_equal(first_tile.image, first_image)
                np.testing.assert_array_equal(second_tile.image, second_image)
                self.assertEqual(puzzle.processor.incorrect_tile_count, 2)

    def test_rotation_changes_pixels_and_returns_true(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                puzzle = Puzzle(make_processor(grid_size))
                action = RotateAction(puzzle)
                self.assertIsInstance(action, PuzzleAction)
                self.assertIs(action.puzzle, puzzle)
                tile = puzzle.get_tile_at((0, 0))
                original = tile.image.copy()

                self.assertTrue(action.apply((0, 0)))
                np.testing.assert_array_equal(tile.image, np.rot90(original, -1))
                self.assertEqual(tile.rotation, 90)
                self.assertFalse(tile.is_correct)
                for turn in range(3):
                    self.assertTrue(action.apply((0, 0)))
                np.testing.assert_array_equal(tile.image, original)
                self.assertTrue(tile.is_correct)

    def test_flip_changes_pixels_and_returns_true(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                puzzle = Puzzle(make_processor(grid_size))
                action = FlipAction(puzzle)
                self.assertIsInstance(action, PuzzleAction)
                self.assertIs(action.puzzle, puzzle)
                tile = puzzle.get_tile_at((0, 0))
                original = tile.image.copy()

                self.assertTrue(action.apply((0, 0)))
                np.testing.assert_array_equal(tile.image, original[:, ::-1])
                self.assertEqual(tile.flip, "horizontal")
                self.assertFalse(tile.is_correct)
                self.assertTrue(action.apply((0, 0)))
                np.testing.assert_array_equal(tile.image, original)
                self.assertTrue(tile.is_correct)


class GameActionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tkinter display unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.gui = PuzzleGUI(self.root)
        dialog_patch = patch("game.game_manager.messagebox.showinfo")
        self.showinfo = dialog_patch.start()
        self.addCleanup(dialog_patch.stop)

    def start_round(self, grid_size):
        processor = make_processor(grid_size)
        # Leave one tile rotated so the game starts with an unfinished board.
        Puzzle(processor).rotate((grid_size - 1, grid_size - 1))
        processor.transformed_image = processor.reassemble_image()
        self.gui.image_processor = processor
        self.gui.original_photo = self.gui.display_image(
            self.gui.canvas_orig, processor.original_image
        )
        self.gui.game_photo = self.gui.display_image(
            self.gui.canvas_game, processor.transformed_image
        )
        self.gui.draw_game_grid(processor.transformed_image)
        return GameManager(self.gui)

    def tile_event(self, manager, row, column):
        image = manager.processor.transformed_image
        height, width = image.shape[:2]
        canvas = self.gui.canvas_game
        left = (int(canvas.cget("width")) - width) // 2
        top = (int(canvas.cget("height")) - height) // 2
        tile_width = width // manager.puzzle.grid_size
        tile_height = height // manager.puzzle.grid_size
        return SimpleNamespace(
            x=left + column * tile_width + tile_width // 2,
            y=top + row * tile_height + tile_height // 2,
        )

    def test_mouse_actions_count_moves_and_clear_hints(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                manager = self.start_round(grid_size)
                first_click = self.tile_event(manager, 0, 0)
                second_click = self.tile_event(manager, 0, 1)
                first_tile = manager.puzzle.get_tile_at((0, 0))
                second_tile = manager.puzzle.get_tile_at((0, 1))
                manager.show_hint()
                hint_tile = manager.hint_tile

                # Selection and deselection preserve the hint and score.
                self.assertEqual(manager.left_click(first_click), "break")
                self.assertEqual(manager.left_click(first_click), "break")
                self.assertEqual(manager.moves, 0)
                self.assertIs(manager.hint_tile, hint_tile)
                self.assertEqual(len(self.gui.canvas_game.find_withtag("hint")), 1)
                self.assertEqual(len(self.gui.canvas_orig.find_withtag("hint")), 1)

                manager.left_click(first_click)
                self.assertEqual(manager.left_click(second_click), "break")
                self.assertEqual(manager.moves, 1)
                self.assertIs(manager.puzzle.get_tile_at((0, 0)), second_tile)
                self.assertIs(manager.puzzle.get_tile_at((0, 1)), first_tile)
                self.assertIsNone(manager.puzzle.selected_position)
                self.assertIsNone(manager.hint_tile)

                manager.show_hint()
                before_rotation = second_tile.image.copy()
                self.assertEqual(manager.right_click(first_click), "break")
                self.assertEqual(manager.moves, 2)
                np.testing.assert_array_equal(
                    second_tile.image, np.rot90(before_rotation, -1)
                )
                self.assertIsNone(manager.hint_tile)

                manager.show_hint()
                before_flip = second_tile.image.copy()
                self.assertEqual(manager.shift_left_click(first_click), "break")
                self.assertEqual(manager.moves, 3)
                self.assertIsNone(manager.puzzle.selected_position)
                np.testing.assert_array_equal(second_tile.image, before_flip[:, ::-1])
                self.assertIsNone(manager.hint_tile)
                self.assertEqual(self.gui.canvas_game.find_withtag("hint"), ())
                self.assertEqual(self.gui.canvas_orig.find_withtag("hint"), ())
                self.assertEqual(manager.hints_used, 3)
                self.assertEqual(self.gui.hint_button.cget("state"), tk.DISABLED)
                self.assertEqual(
                    self.gui.score_label.cget("text"), "Moves: 3 | Incorrect: 3"
                )
                np.testing.assert_array_equal(
                    manager.processor.transformed_image,
                    manager.processor.reassemble_image(),
                )

    def test_off_image_clicks_do_not_change_tiles_or_hints(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                manager = self.start_round(grid_size)
                manager.show_hint()
                hint_tile = manager.hint_tile
                before = manager.processor.transformed_image.copy()
                first_click = self.tile_event(manager, 0, 0)
                tile_side = before.shape[0] // grid_size
                left = first_click.x - tile_side // 2
                top = first_click.y - tile_side // 2
                outside_events = [
                    SimpleNamespace(x=left - 1, y=first_click.y),
                    SimpleNamespace(x=left + before.shape[1], y=first_click.y),
                    SimpleNamespace(x=first_click.x, y=top - 1),
                    SimpleNamespace(x=first_click.x, y=top + before.shape[0]),
                ]
                for click_handler in (
                    manager.left_click, manager.right_click, manager.shift_left_click
                ):
                    for event in outside_events:
                        self.assertEqual(click_handler(event), "break")
                self.assertEqual(manager.moves, 0)
                self.assertIsNone(manager.puzzle.selected_position)
                self.assertIs(manager.hint_tile, hint_tile)
                np.testing.assert_array_equal(manager.processor.reassemble_image(), before)
                self.assertEqual(manager.processor.incorrect_tile_count, 1)

    def test_completion_counts_once_then_rejects_input(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                self.showinfo.reset_mock()
                manager = self.start_round(grid_size)
                event = self.tile_event(manager, grid_size - 1, grid_size - 1)
                for turn in range(3):
                    manager.right_click(event)
                self.assertTrue(manager.finished)
                self.assertEqual(manager.moves, 3)
                self.assertEqual(manager.processor.incorrect_tile_count, 0)
                np.testing.assert_array_equal(
                    manager.processor.transformed_image, manager.processor.original_image
                )
                self.showinfo.assert_called_once()
                for click_handler in (
                    manager.left_click, manager.right_click, manager.shift_left_click
                ):
                    self.assertEqual(click_handler(event), "break")
                self.assertEqual(manager.moves, 3)
                self.assertIsNone(manager.puzzle.selected_position)
                np.testing.assert_array_equal(
                    manager.processor.reassemble_image(), manager.processor.original_image
                )
                self.showinfo.assert_called_once()

    def test_solve_clears_moves_selection_and_hints(self):
        manager = self.start_round(3)
        manager.right_click(self.tile_event(manager, 0, 0))
        manager.left_click(self.tile_event(manager, 0, 1))
        manager.show_hint()
        manager.solve_puzzle()
        self.assertTrue(manager.finished)
        self.assertEqual(manager.moves, 0)
        self.assertIsNone(manager.puzzle.selected_position)
        self.assertIsNone(manager.hint_tile)
        self.assertEqual(manager.processor.incorrect_tile_count, 0)
        self.assertEqual(self.gui.score_label.cget("text"), "Moves: 0 | Incorrect: 0")
        self.assertEqual(self.gui.hint_button.cget("state"), tk.DISABLED)
        self.assertEqual(self.gui.solve_button.cget("state"), tk.DISABLED)
        np.testing.assert_array_equal(
            manager.processor.transformed_image, manager.processor.original_image
        )
        self.showinfo.assert_called_once()


if __name__ == "__main__":
    unittest.main()
