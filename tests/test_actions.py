"""Check puzzle actions and their effect on game scoring and hints."""

import random
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from game.game_manager import GameManager
from gui.main_window import PuzzleGUI
from image_processing.image_processor import ImageProcessor, ImageTile
from puzzle.actions import FlipAction, PuzzleAction, RotateAction, SelectAction
from puzzle.puzzle import Puzzle


def make_processor(grid_size, tile_side=4):
    """Create a small board with distinct pixels, without reading image files."""
    side = grid_size * tile_side
    image = np.arange(side * side * 3).reshape(side, side, 3).astype(np.uint8)
    processor = ImageProcessor()
    processor.grid_size = grid_size
    processor.original_image = image.copy()
    processor.tiles = processor.slice_image(image, grid_size)
    processor.transformed_image = processor.reassemble_image()
    return processor


class PuzzleActionTests(unittest.TestCase):
    def test_mixed_rotations_and_flips_keep_orientation_in_sync(self):
        original = np.arange(4 * 4 * 3, dtype=np.uint8).reshape(4, 4, 3)
        sequences = (
            ("rotate", "flip"),
            ("flip", "rotate"),
            ("rotate", "flip", "rotate", "flip"),
            ("flip", "rotate", "flip", "rotate"),
            ("rotate", "rotate", "flip", "flip", "rotate", "rotate"),
        )
        for rotation in (0, 90, 180, 270):
            for flip in (None, "horizontal", "vertical"):
                for sequence in sequences:
                    with self.subTest(rotation=rotation, flip=flip, sequence=sequence):
                        processor = make_processor(3)
                        pixels = np.rot90(original, -rotation // 90).copy()
                        if flip is not None:
                            pixels = np.flip(pixels, 1 if flip == "horizontal" else 0).copy()
                        tile = ImageTile(0, (0, 0), (0, 0), pixels, rotation, flip)
                        processor.tiles[0] = tile
                        puzzle = Puzzle(processor)
                        expected = pixels.copy()
                        for operation in sequence:
                            if operation == "rotate":
                                puzzle.rotate((0, 0))
                                expected = np.rot90(expected, -1)
                            else:
                                puzzle.flip((0, 0))
                                expected = np.flip(expected, 1)
                            np.testing.assert_array_equal(tile.image, expected)
                            represented = np.rot90(original, -tile.rotation // 90)
                            if tile.flip is not None:
                                axis = 1 if tile.flip == "horizontal" else 0
                                represented = np.flip(represented, axis)
                            np.testing.assert_array_equal(tile.image, represented)
                            self.assertEqual(tile.is_correct, np.array_equal(expected, original))

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

    def start_round(self, grid_size, tile_side=4):
        processor = make_processor(grid_size, tile_side)
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

    def test_exact_tile_boundaries_and_last_pixel_select_the_right_tile(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                manager = self.start_round(grid_size)
                first = self.tile_event(manager, 0, 0)
                left = first.x - 2
                top = first.y - 2
                for row in range(grid_size):
                    for column in range(grid_size):
                        # Test both the first and last pixel of every tile.
                        for offset in (0, 3):
                            event = SimpleNamespace(
                                x=left + column * 4 + offset,
                                y=top + row * 4 + offset,
                            )
                            manager.left_click(event)
                            self.assertEqual(manager.puzzle.selected_position, (row, column))
                            self.assertEqual(len(self.gui.canvas_game.find_withtag("selection")), 1)
                            manager.left_click(event)
                            self.assertIsNone(manager.puzzle.selected_position)
                            self.assertEqual(self.gui.canvas_game.find_withtag("selection"), ())
                self.assertEqual(manager.moves, 0)

    def test_full_size_board_clicks_match_rendered_tile_edges(self):
        for grid_size, tile_side in ((3, 133), (4, 100), (5, 80)):
            with self.subTest(grid_size=grid_size):
                manager = self.start_round(grid_size, tile_side)
                canvas = self.gui.canvas_game
                # Read Tkinter's actual image bounds instead of assuming its placement.
                image_item = next(item for item in canvas.find_all()
                                  if canvas.type(item) == "image")
                left, top, right, bottom = canvas.bbox(image_item)
                for row in range(grid_size):
                    for column in range(grid_size):
                        for x_offset, y_offset in ((0, 0), (tile_side - 1, 0),
                                                   (0, tile_side - 1),
                                                   (tile_side - 1, tile_side - 1)):
                            event = SimpleNamespace(
                                x=left + column * tile_side + x_offset,
                                y=top + row * tile_side + y_offset,
                            )
                            manager.left_click(event)
                            self.assertEqual(manager.puzzle.selected_position, (row, column))
                            selection = canvas.find_withtag("selection")[0]
                            self.assertEqual(canvas.coords(selection), [
                                left + column * tile_side, top + row * tile_side,
                                left + (column + 1) * tile_side, top + (row + 1) * tile_side,
                            ])
                            manager.left_click(event)
                for event in (SimpleNamespace(x=left - 1, y=top),
                              SimpleNamespace(x=right, y=top),
                              SimpleNamespace(x=left, y=top - 1),
                              SimpleNamespace(x=left, y=bottom)):
                    manager.left_click(event)
                    self.assertIsNone(manager.puzzle.selected_position)
                self.assertEqual(manager.moves, 0)

    def test_odd_sized_board_grid_ticks_and_hints_match_image_bounds(self):
        manager = self.start_round(3, 133)
        canvas = self.gui.canvas_game
        image_item = next(item for item in canvas.find_all() if canvas.type(item) == "image")
        left, top, right, bottom = canvas.bbox(image_item)
        expected_lines = []
        for boundary in (1, 2):
            x = left + boundary * 133
            y = top + boundary * 133
            expected_lines.append([x, top, x, bottom])
            expected_lines.append([left, y, right, y])
        lines = [canvas.coords(item) for item in canvas.find_all() if canvas.type(item) == "line"]
        self.assertEqual(lines, expected_lines)
        expected_ticks = []
        for tile in manager.processor.tiles:
            if tile.is_correct:
                row, column = tile.current_position
                expected_ticks.append([left + column * 133 + 14, top + row * 133 + 14])
        self.assertEqual([canvas.coords(item) for item in canvas.find_withtag("tick")],
                         expected_ticks)

        tile = manager.puzzle.get_tile_at((0, 0))
        manager.left_click(SimpleNamespace(x=left + 20, y=top + 20))
        manager.left_click(SimpleNamespace(x=left + 153, y=top + 20))
        with patch("game.game_manager.random.choice", return_value=tile):
            manager.show_hint()
        for hint_canvas, position in ((canvas, (0, 1)), (self.gui.canvas_orig, (0, 0))):
            image_item = next(item for item in hint_canvas.find_all()
                              if hint_canvas.type(item) == "image")
            hint_left, hint_top, _, _ = hint_canvas.bbox(image_item)
            row, column = position
            centre_x = hint_left + column * 133 + 66
            centre_y = hint_top + row * 133 + 66
            circle = hint_canvas.find_withtag("hint")[0]
            self.assertEqual(hint_canvas.coords(circle),
                             [centre_x - 33, centre_y - 33, centre_x + 33, centre_y + 33])

    def test_hint_limit_cannot_be_bypassed_by_calling_the_handler(self):
        manager = self.start_round(3)
        for used in range(1, 4):
            manager.show_hint()
            self.assertEqual(manager.hints_used, used)
            self.assertEqual(self.gui.hint_button.cget("text"), f"Hint ({3 - used})")
            self.assertEqual(len(self.gui.canvas_game.find_withtag("hint")), 1)
            self.assertEqual(len(self.gui.canvas_orig.find_withtag("hint")), 1)
        hint_tile = manager.hint_tile
        with patch("game.game_manager.random.choice") as choose:
            manager.show_hint()
            choose.assert_not_called()
        self.assertIs(manager.hint_tile, hint_tile)
        self.assertEqual(manager.hints_used, 3)
        self.assertEqual(self.gui.hint_button.cget("state"), tk.DISABLED)
        manager.right_click(self.tile_event(manager, 0, 0))
        manager.show_hint()
        self.assertIsNone(manager.hint_tile)
        self.assertEqual(manager.hints_used, 3)
        self.assertEqual(self.gui.canvas_game.find_withtag("hint"), ())

    def test_hint_marks_current_and_home_positions_without_changing_pixels(self):
        manager = self.start_round(3)
        tile = manager.puzzle.get_tile_at((0, 0))
        manager.left_click(self.tile_event(manager, 0, 0))
        manager.left_click(self.tile_event(manager, 1, 2))
        original = manager.processor.original_image.copy()
        transformed = manager.processor.transformed_image.copy()
        with patch("game.game_manager.random.choice", return_value=tile) as choose:
            manager.show_hint()
        self.assertTrue(all(not candidate.is_correct for candidate in choose.call_args.args[0]))
        self.assertIs(manager.hint_tile, tile)
        for canvas, image, position in (
            (self.gui.canvas_game, transformed, (1, 2)),
            (self.gui.canvas_orig, original, (0, 0)),
        ):
            row, column = position
            height, width = image.shape[:2]
            left = (int(canvas.cget("width")) - width) // 2
            top = (int(canvas.cget("height")) - height) // 2
            tile_width = width // manager.puzzle.grid_size
            tile_height = height // manager.puzzle.grid_size
            centre_x = left + column * tile_width + tile_width // 2
            centre_y = top + row * tile_height + tile_height // 2
            radius = min(tile_width, tile_height) // 4
            circle = canvas.find_withtag("hint")[0]
            self.assertEqual(canvas.coords(circle),
                             [centre_x - radius, centre_y - radius,
                              centre_x + radius, centre_y + radius])
        np.testing.assert_array_equal(manager.processor.original_image, original)
        np.testing.assert_array_equal(manager.processor.transformed_image, transformed)
        np.testing.assert_array_equal(manager.processor.reassemble_image(), transformed)

    def test_ticks_require_correct_position_and_orientation(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                manager = self.start_round(grid_size)
                total = grid_size * grid_size
                self.assertEqual(len(self.gui.canvas_game.find_withtag("tick")), total - 1)
                manager.left_click(self.tile_event(manager, 0, 0))
                manager.left_click(self.tile_event(manager, 0, 1))
                manager.shift_left_click(self.tile_event(manager, 1, 0))
                self.assertEqual(manager.processor.incorrect_tile_count, 4)
                ticks = self.gui.canvas_game.find_withtag("tick")
                self.assertEqual(len(ticks), total - 4)
                first = self.tile_event(manager, 0, 0)
                left = first.x - 2
                top = first.y - 2
                correct_positions = []
                for tile in manager.processor.tiles:
                    if tile.is_correct:
                        row, column = tile.current_position
                        correct_positions.append([left + column * 4 + 2, top + row * 4 + 2])
                self.assertEqual([self.gui.canvas_game.coords(tick) for tick in ticks], correct_positions)
                self.assertFalse(manager.finished)

    def test_cancelled_and_invalid_loads_preserve_the_current_round(self):
        manager = self.start_round(3)
        self.gui.game_manager = manager
        manager.right_click(self.tile_event(manager, 0, 0))
        manager.left_click(self.tile_event(manager, 0, 1))
        manager.show_hint()
        tiles = manager.processor.tiles
        before = manager.processor.transformed_image.copy()
        hint_tile = manager.hint_tile
        game_items = self.gui.canvas_game.find_all()
        original_items = self.gui.canvas_orig.find_all()
        score = self.gui.score_label.cget("text")
        with tempfile.TemporaryDirectory() as directory:
            corrupt = Path(directory) / "corrupt.png"
            corrupt.write_bytes(b"not an image")
            for file_path in ("", str(corrupt), str(Path(directory) / "missing.png")):
                with self.subTest(file_path=file_path):
                    with patch("gui.main_window.filedialog.askopenfilename", return_value=file_path), \
                            patch("gui.main_window.messagebox.showerror") as showerror:
                        self.gui.load_image()
                    self.assertEqual(showerror.call_count, 1 if file_path else 0)
                    self.assertIs(self.gui.game_manager, manager)
                    self.assertIs(manager.processor.tiles, tiles)
                    self.assertEqual(manager.moves, 1)
                    self.assertEqual(manager.hints_used, 1)
                    self.assertIs(manager.hint_tile, hint_tile)
                    self.assertEqual(manager.puzzle.selected_position, (0, 1))
                    self.assertEqual(self.gui.canvas_game.find_all(), game_items)
                    self.assertEqual(self.gui.canvas_orig.find_all(), original_items)
                    self.assertEqual(self.gui.score_label.cget("text"), score)
                    np.testing.assert_array_equal(manager.processor.transformed_image, before)

    def test_loading_another_image_resets_active_and_finished_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new.png"
            image = np.arange(12 * 18 * 3).reshape(12, 18, 3).astype(np.uint8)
            success, encoded = cv2.imencode(".png", image)
            self.assertTrue(success)
            encoded.tofile(str(path))
            for finished in (False, True):
                for grid_size in (3, 4, 5):
                    with self.subTest(finished=finished, grid_size=grid_size):
                        old_manager = self.start_round(3)
                        self.gui.game_manager = old_manager
                        old_manager.right_click(self.tile_event(old_manager, 0, 0))
                        old_manager.left_click(self.tile_event(old_manager, 0, 1))
                        for hint in range(3):
                            old_manager.show_hint()
                        if finished:
                            old_manager.solve_puzzle()
                        self.gui.selected_size.set(f"{grid_size}x{grid_size}")
                        self.gui.image_processor.rng = random.Random(42)
                        self.showinfo.reset_mock()
                        with patch("gui.main_window.filedialog.askopenfilename", return_value=str(path)):
                            self.gui.load_image()
                        manager = self.gui.game_manager
                        self.assertIsNot(manager, old_manager)
                        self.assertEqual(manager.puzzle.grid_size, grid_size)
                        self.assertEqual(manager.moves, 0)
                        self.assertEqual(manager.hints_used, 0)
                        self.assertIsNone(manager.hint_tile)
                        self.assertIsNone(manager.puzzle.selected_position)
                        self.assertFalse(manager.finished)
                        self.assertEqual(self.gui.canvas_game.find_withtag("selection"), ())
                        self.assertEqual(self.gui.canvas_game.find_withtag("hint"), ())
                        self.assertEqual(self.gui.canvas_orig.find_withtag("hint"), ())
                        self.assertEqual(self.gui.hint_button.cget("state"), tk.NORMAL)
                        self.assertEqual(self.gui.hint_button.cget("text"), "Hint (3)")
                        self.assertEqual(self.gui.solve_button.cget("state"), tk.NORMAL)
                        self.assertEqual(self.gui.score_label.cget("text"),
                                         f"Moves: 0 | Incorrect: {manager.processor.incorrect_tile_count}")
                        self.showinfo.assert_not_called()
                        # Button commands must now operate on the new manager.
                        self.gui.hint_button.invoke()
                        self.assertEqual(manager.hints_used, 1)
                        self.gui.solve_button.invoke()
                        self.assertTrue(manager.finished)
                        self.assertEqual(manager.processor.incorrect_tile_count, 0)
                        self.showinfo.assert_called_once()

    def test_finished_round_ignores_hint_and_repeated_solve(self):
        manager = self.start_round(3)
        manager.solve_puzzle()
        before = manager.processor.transformed_image.copy()
        manager.show_hint()
        manager.solve_puzzle()
        self.assertEqual(manager.hints_used, 0)
        self.assertIsNone(manager.hint_tile)
        self.assertEqual(self.gui.canvas_game.find_withtag("hint"), ())
        self.assertEqual(manager.moves, 0)
        np.testing.assert_array_equal(manager.processor.transformed_image, before)
        self.showinfo.assert_called_once()


if __name__ == "__main__":
    unittest.main()
