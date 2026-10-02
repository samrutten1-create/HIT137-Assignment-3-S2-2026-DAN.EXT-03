"""Check image preparation, scrambling, and restoration without a GUI."""

import random
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from image_processing.image_processor import ImageProcessingError, ImageProcessor


class ImageProcessorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.image = np.arange(18 * 30 * 3).reshape(18, 30, 3).astype(np.uint8)
        self.path = self.write_image("picture.png", self.image)

    def write_image(self, name, image):
        path = self.directory / name
        success, encoded = cv2.imencode(path.suffix, image)
        self.assertTrue(success)
        encoded.tofile(str(path))
        return path

    def test_supported_files_and_unicode_paths_load_as_bgr(self):
        colour = np.full((12, 15, 3), (24, 96, 180), dtype=np.uint8)
        for extension in (".png", ".bmp", ".jpg", ".jpeg"):
            with self.subTest(extension=extension):
                path = self.write_image("café_图片" + extension, colour)
                loaded = ImageProcessor.load_image(path)
                self.assertEqual(loaded.shape, colour.shape)
                self.assertEqual(loaded.dtype, np.uint8)
                # JPEG is lossy, so allow a small colour difference.
                tolerance = 2 if extension in (".jpg", ".jpeg") else 0
                np.testing.assert_allclose(loaded, colour, atol=tolerance)

    def test_grayscale_and_transparent_images_become_three_channels(self):
        grayscale = np.arange(60, dtype=np.uint8).reshape(6, 10)
        transparent = np.full((6, 10, 4), (20, 60, 100, 128), dtype=np.uint8)
        for name, image in (("gray.png", grayscale), ("alpha.png", transparent)):
            with self.subTest(name=name):
                loaded = ImageProcessor.load_image(self.write_image(name, image))
                self.assertEqual(loaded.shape, (6, 10, 3))
                if name == "gray.png":
                    for channel in range(3):
                        np.testing.assert_array_equal(loaded[:, :, channel], grayscale)
                else:
                    np.testing.assert_array_equal(loaded, transparent[:, :, :3])

    def test_missing_empty_and_corrupt_files_raise_friendly_errors(self):
        empty = self.directory / "empty.png"
        empty.write_bytes(b"")
        corrupt = self.directory / "corrupt.png"
        corrupt.write_bytes(b"This is not an image.")
        for path in ("", self.directory / "missing.png", self.directory, empty, corrupt):
            with self.subTest(path=path):
                with self.assertRaises(ImageProcessingError):
                    ImageProcessor.load_image(path)

    def test_grid_size_accepts_supported_labels_and_rejects_invalid_values(self):
        for size in (3, 4, 5):
            for value in (size, str(size), f"{size}x{size}", f" {size} X {size} "):
                with self.subTest(value=value):
                    self.assertEqual(ImageProcessor.parse_grid_size(value), size)
        for value in (True, False, None, 3.0, 0, 2, 6, "", "3x4", "3x3x3", "three"):
            with self.subTest(value=value):
                with self.assertRaises(ImageProcessingError):
                    ImageProcessor.parse_grid_size(value)

    def test_resize_preserves_aspect_ratio_and_centres_padding(self):
        colour = (30, 80, 150)
        padding = (2, 4, 6)
        processor = ImageProcessor(max_size=(41, 37), padding_colour=padding)
        for grid_size in (3, 4, 5):
            for height, width in ((8, 16), (16, 8), (10, 10), (80, 160), (1, 200)):
                with self.subTest(grid_size=grid_size, shape=(height, width)):
                    image = np.full((height, width, 3), colour, dtype=np.uint8)
                    before = image.copy()
                    prepared = processor.resize_and_pad(image, grid_size)
                    side = 37 - 37 % grid_size
                    self.assertEqual(prepared.shape, (side, side, 3))
                    scale = side / max(height, width)
                    content_height = max(1, round(height * scale))
                    content_width = max(1, round(width * scale))
                    top = (side - content_height) // 2
                    left = (side - content_width) // 2
                    expected = np.full((side, side, 3), padding, dtype=np.uint8)
                    expected[top:top + content_height, left:left + content_width] = colour
                    np.testing.assert_array_equal(prepared, expected)
                    np.testing.assert_array_equal(image, before)

    def test_invalid_arrays_and_too_small_canvas_are_rejected(self):
        processor = ImageProcessor()
        invalid_images = (None, [], np.empty((0, 3, 3)), np.zeros((4, 4)),
                          np.zeros((4, 4, 4)))
        for image in invalid_images:
            with self.subTest(shape=getattr(image, "shape", None)):
                with self.assertRaises(ImageProcessingError):
                    processor.resize_and_pad(image, 3)
                with self.assertRaises(ImageProcessingError):
                    processor.slice_image(image, 3)
        with self.assertRaises(ImageProcessingError):
            ImageProcessor(max_size=(2, 2)).resize_and_pad(self.image, 3)

    def test_slicing_is_row_major_and_tiles_do_not_share_source_pixels(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                side = grid_size * 4
                image = np.arange(side * side * 3).reshape(side, side, 3).astype(np.uint8)
                before = image.copy()
                processor = ImageProcessor()
                processor.grid_size = grid_size
                processor.tiles = processor.slice_image(image, grid_size)
                for index, tile in enumerate(processor.tiles):
                    row, column = divmod(index, grid_size)
                    self.assertEqual(tile.tile_id, index)
                    self.assertEqual(tile.home_position, (row, column))
                    self.assertEqual(tile.current_position, (row, column))
                    self.assertTrue(tile.is_correct)
                    np.testing.assert_array_equal(
                        tile.image, image[row * 4:(row + 1) * 4, column * 4:(column + 1) * 4]
                    )
                    self.assertFalse(np.shares_memory(tile.image, image))
                assembled = processor.reassemble_image()
                np.testing.assert_array_equal(assembled, image)
                assembled[:] = 0
                np.testing.assert_array_equal(processor.reassemble_image(), image)
                processor.tiles[0].image[:] = 0
                np.testing.assert_array_equal(image, before)

    def test_unprepared_boards_and_invalid_tile_lists_are_rejected(self):
        processor = ImageProcessor()
        for operation in (processor.reassemble_image, processor.apply_random_transformations,
                          processor.solved_image):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(ImageProcessingError):
                    operation()
        with self.assertRaises(ImageProcessingError):
            processor.slice_image(self.image)
        with self.assertRaises(ImageProcessingError):
            processor.slice_image(np.zeros((10, 10, 3), dtype=np.uint8), 3)
        processor.grid_size = 3
        for tiles in ([], [object()] * 9):
            for operation in (processor.reassemble_image, processor.apply_random_transformations):
                with self.subTest(operation=operation.__name__, count=len(tiles)):
                    with self.assertRaises(ImageProcessingError):
                        operation(tiles)

    def test_scrambles_target_unique_tiles_and_match_logged_pixels(self):
        for grid_size, count in ((3, 6), (4, 12), (5, 20)):
            for seed in range(10):
                with self.subTest(grid_size=grid_size, seed=seed):
                    processor = ImageProcessor(max_size=(60, 60), rng=random.Random(seed))
                    original, transformed = processor.process_image(self.path, grid_size)
                    canonical = processor.slice_image(original, grid_size)
                    log = processor.transformation_log
                    self.assertEqual(len(log), count)
                    self.assertEqual({step.kind for step in log}, {"swap", "rotate", "flip"})
                    targets = []
                    for step in log:
                        targets.extend(step.tile_ids)
                    self.assertEqual(len(targets), count + 1)
                    self.assertEqual(len(set(targets)), len(targets))
                    self.assertEqual(processor.incorrect_tile_count, len(targets))
                    expected_positions = list(range(grid_size * grid_size))
                    expected_pixels = [tile.image.copy() for tile in canonical]
                    expected_rotations = [0] * (grid_size * grid_size)
                    expected_flips = [None] * (grid_size * grid_size)
                    for step in log:
                        if step.kind == "swap":
                            first, second = step.tile_ids
                            expected_positions[first], expected_positions[second] = second, first
                        elif step.kind == "rotate":
                            self.assertIn(step.value, (90, 180, 270))
                            tile_id = step.tile_ids[0]
                            expected_pixels[tile_id] = np.rot90(expected_pixels[tile_id], -step.value // 90)
                            expected_rotations[tile_id] = step.value
                        else:
                            self.assertIn(step.value, ("horizontal", "vertical"))
                            tile_id = step.tile_ids[0]
                            axis = 1 if step.value == "horizontal" else 0
                            expected_pixels[tile_id] = np.flip(expected_pixels[tile_id], axis)
                            expected_flips[tile_id] = step.value
                    for index, tile in enumerate(processor.tiles):
                        self.assertEqual(tile.tile_id, expected_positions[index])
                        self.assertEqual(tile.current_position, divmod(index, grid_size))
                        self.assertEqual(tile.home_position, divmod(tile.tile_id, grid_size))
                        self.assertEqual(tile.rotation, expected_rotations[tile.tile_id])
                        self.assertEqual(tile.flip, expected_flips[tile.tile_id])
                        np.testing.assert_array_equal(tile.image, expected_pixels[tile.tile_id])
                    np.testing.assert_array_equal(transformed, processor.reassemble_image())
                    np.testing.assert_array_equal(processor.original_image, original)

    def test_seeded_scrambles_are_repeatable(self):
        first = ImageProcessor(rng=random.Random(42))
        second = ImageProcessor(rng=random.Random(42))
        first.process_image(self.path, 4)
        second.process_image(self.path, 4)
        self.assertEqual(first.transformation_log, second.transformation_log)
        np.testing.assert_array_equal(first.transformed_image, second.transformed_image)

    def test_solve_restores_every_tile_and_returned_images_are_independent(self):
        for grid_size in (3, 4, 5):
            with self.subTest(grid_size=grid_size):
                processor = ImageProcessor(rng=random.Random(42))
                original, transformed = processor.process_image(self.path, grid_size)
                expected = original.copy()
                original[:] = 0
                transformed[:] = 0
                np.testing.assert_array_equal(processor.original_image, expected)
                np.testing.assert_array_equal(processor.transformed_image, processor.reassemble_image())
                solved = processor.solved_image()
                np.testing.assert_array_equal(solved, expected)
                np.testing.assert_array_equal(processor.reassemble_image(), expected)
                self.assertEqual(processor.incorrect_tile_count, 0)
                self.assertEqual(processor.transformation_log, [])
                for index, tile in enumerate(processor.tiles):
                    self.assertEqual(tile.tile_id, index)
                    self.assertEqual(tile.current_position, tile.home_position)
                    self.assertEqual(tile.rotation, 0)
                    self.assertIsNone(tile.flip)
                solved[:] = 0
                processor.tiles[0].image[:] = 0
                np.testing.assert_array_equal(processor.original_image, expected)
                np.testing.assert_array_equal(processor.transformed_image, expected)

    def test_failed_load_keeps_the_existing_board(self):
        processor = ImageProcessor(rng=random.Random(42))
        processor.process_image(self.path, 3)
        tiles = processor.tiles
        original = processor.original_image.copy()
        transformed = processor.transformed_image.copy()
        log = list(processor.transformation_log)
        for path, grid_size in ((self.directory / "missing.png", 4), (self.path, "3x4")):
            with self.subTest(path=path, grid_size=grid_size):
                with self.assertRaises(ImageProcessingError):
                    processor.process_image(path, grid_size)
                self.assertEqual(processor.grid_size, 3)
                self.assertIs(processor.tiles, tiles)
                self.assertEqual(processor.transformation_log, log)
                np.testing.assert_array_equal(processor.original_image, original)
                np.testing.assert_array_equal(processor.transformed_image, transformed)


if __name__ == "__main__":
    unittest.main()
