from dataclasses import dataclass
from pathlib import Path
import random
from typing import List, Optional, Sequence, Tuple, Union
import cv2
import numpy as np
GridSize = Union[int, str]
Position = Tuple[int, int]
class ImageProcessingError(ValueError):
    """Raised when an image cannot be loaded or prepared for the puzzle."""
@dataclass
class ImageTile:
    """A tile image plus the state needed by the puzzle/game layer.
    ``tile_id`` and ``home_position`` never change.  ``current_position`` is
    refreshed after scrambling so that the game engine can determine whether
    a tile is in its correct location.
    """
    tile_id: int
    home_position: Position
    current_position: Position
    image: np.ndarray
    rotation: int = 0
    flip: Optional[str] = None
    @property
    def is_correct(self) -> bool:
        """Return ``True`` only when position and orientation are correct."""

        return (
            self.current_position == self.home_position
            and self.rotation % 360 == 0
            and self.flip is None
        )
@dataclass(frozen=True)
class Transformation:
    """Description of one scrambling operation, useful for testing/debugging."""
    kind: str
    tile_ids: Tuple[int, ...]
    value: Optional[Union[int, str]] = None
class ImageProcessor:
    """Load, size, split, transform, and reassemble puzzle images.
    Args:
        max_size: Maximum ``(width, height)`` available for either canvas.
        padding_colour: OpenCV BGR colour used around non-square images.
        rng: Optional random-number generator.  Supplying ``random.Random``
            with a seed makes scrambling repeatable in tests.
    """
    GRID_SIZES = (3, 4, 5)
    TRANSFORMATION_COUNTS = {3: 6, 4: 12, 5: 20}
    def __init__(
        self,
        max_size: Tuple[int, int] = (400, 400),
        padding_colour: Tuple[int, int, int] = (0, 0, 0),
        rng: Optional[random.Random] = None,
    ) -> None:
        if len(max_size) != 2 or max_size[0] <= 0 or max_size[1] <= 0:
            raise ValueError("max_size must contain two positive integers")
        if len(padding_colour) != 3 or any(
            channel < 0 or channel > 255 for channel in padding_colour
        ):
            raise ValueError("padding_colour must be a three-channel BGR colour")
        self.max_size = (int(max_size[0]), int(max_size[1]))
        self.padding_colour = tuple(int(channel) for channel in padding_colour)
        self.rng = rng if rng is not None else random.Random()
        self.grid_size: Optional[int] = None
        self.original_image: Optional[np.ndarray] = None
        self.transformed_image: Optional[np.ndarray] = None
        self.tiles: List[ImageTile] = []
        self.transformation_log: List[Transformation] = []
    @staticmethod
    def parse_grid_size(grid_size: GridSize) -> int:
        """Convert ``3``, ``"3"``, or ``"3x3"`` into a validated integer."""
        if isinstance(grid_size, bool):
            raise ImageProcessingError("Grid size must be 3x3, 4x4, or 5x5")
        if isinstance(grid_size, int):
            size = grid_size
        elif isinstance(grid_size, str):
            normalised = grid_size.strip().lower().replace(" ", "")
            parts = normalised.split("x")
            if len(parts) == 1 and parts[0].isdigit():
                size = int(parts[0])
            elif (
                len(parts) == 2
                and parts[0].isdigit()
                and parts[1].isdigit()
                and parts[0] == parts[1]
            ):
                size = int(parts[0])
            else:
                raise ImageProcessingError(
                    "Grid size must be 3x3, 4x4, or 5x5"
                )
        else:
            raise ImageProcessingError("Grid size must be 3x3, 4x4, or 5x5")

        if size not in ImageProcessor.GRID_SIZES:
            raise ImageProcessingError("Grid size must be 3x3, 4x4, or 5x5")
        return size

    @staticmethod
    def load_image(file_path: Union[str, Path]) -> np.ndarray:
        """Load an image from disk as a three-channel OpenCV BGR array.
        ``np.fromfile`` plus ``cv2.imdecode`` is used instead of ``cv2.imread``
        so paths containing non-ASCII characters also work on Windows.
        """

        if not file_path:
            raise ImageProcessingError("No image file was selected")

        path = Path(file_path)
        if not path.is_file():
            raise ImageProcessingError(f"Image file does not exist: {path}")

        try:
            encoded_image = np.fromfile(str(path), dtype=np.uint8)
            image = cv2.imdecode(encoded_image, cv2.IMREAD_COLOR)
        except (OSError, ValueError, cv2.error) as exc:
            raise ImageProcessingError(f"Could not read image: {path.name}") from exc

        if image is None or image.size == 0:
            raise ImageProcessingError(
                f"The selected file is not a supported image: {path.name}"
            )
        return image

    def resize_and_pad(self, image: np.ndarray, grid_size: GridSize) -> np.ndarray:
        """Fit an image to the canvas and centre-pad it to square dimensions.

        The output side is the largest value that fits ``max_size`` and divides
        exactly by the selected grid size.  Making the board square also keeps
        every tile square, so 90-degree rotations never distort tile geometry.
        """

        size = self.parse_grid_size(grid_size)
        self._validate_image_array(image)

        target_side = min(self.max_size)
        target_side -= target_side % size
        if target_side < size:
            raise ImageProcessingError(
                "Canvas size is too small for the selected puzzle grid"
            )

        height, width = image.shape[:2]
        scale = min(target_side / width, target_side / height)
        resized_width = max(1, min(target_side, int(round(width * scale))))
        resized_height = max(1, min(target_side, int(round(height * scale))))

        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        resized = cv2.resize(
            image,
            (resized_width, resized_height),
            interpolation=interpolation,
        )

        horizontal_padding = target_side - resized_width
        vertical_padding = target_side - resized_height
        left = horizontal_padding // 2
        right = horizontal_padding - left
        top = vertical_padding // 2
        bottom = vertical_padding - top

        return cv2.copyMakeBorder(
            resized,
            top,
            bottom,
            left,
            right,
            cv2.BORDER_CONSTANT,
            value=self.padding_colour,
        )

    def slice_image(
        self, image: np.ndarray, grid_size: Optional[GridSize] = None
    ) -> List[ImageTile]:
        """Cut an evenly divisible image into a row-major master tile list."""

        self._validate_image_array(image)
        if grid_size is None:
            if self.grid_size is None:
                raise ImageProcessingError("A grid size has not been selected")
            size = self.grid_size
        else:
            size = self.parse_grid_size(grid_size)

        height, width = image.shape[:2]
        if height % size != 0 or width % size != 0:
            raise ImageProcessingError(
                "Image dimensions must divide evenly by the selected grid size"
            )

        tile_height = height // size
        tile_width = width // size
        tiles: List[ImageTile] = []

        for row in range(size):
            for column in range(size):
                y_start = row * tile_height
                x_start = column * tile_width
                tile_image = image[
                    y_start : y_start + tile_height,
                    x_start : x_start + tile_width,
                ].copy()
                tile_id = row * size + column
                position = (row, column)
                tiles.append(
                    ImageTile(
                        tile_id=tile_id,
                        home_position=position,
                        current_position=position,
                        image=tile_image,
                    )
                )

        return tiles

    def apply_random_transformations(
        self, tiles: Optional[List[ImageTile]] = None
    ) -> List[ImageTile]:
        """Scramble distinct tiles using swaps, rotations, and flips.

        Exactly 6, 12, or 20 operations are applied for 3x3, 4x4, and 5x5
        puzzles respectively.  There is one swap (which consumes two unique
        tiles); every other operation consumes one unique tile.  No tile is
        targeted twice, and every scramble contains all three required
        transformation types.
        """

        board = self.tiles if tiles is None else tiles
        if self.grid_size is None:
            raise ImageProcessingError("A grid size has not been selected")
        self._validate_tile_list(board, self.grid_size)

        operation_count = self.TRANSFORMATION_COUNTS[self.grid_size]
        targeted_tile_count = operation_count + 1  # A swap targets two tiles.
        selected_tiles = self.rng.sample(board, targeted_tile_count)
        self.rng.shuffle(selected_tiles)
        self.transformation_log = []

        # Guarantee that every load uses all three required transformation
        # families while still randomising the affected tiles and variants.
        self._swap_tiles(board, selected_tiles[0], selected_tiles[1])
        self._rotate_tile(selected_tiles[2])
        self._flip_tile(selected_tiles[3])

        for tile in selected_tiles[4:]:
            if self.rng.choice(("rotate", "flip")) == "rotate":
                self._rotate_tile(tile)
            else:
                self._flip_tile(tile)

        self._refresh_positions(board, self.grid_size)
        return board

    def reassemble_image(
        self, tiles: Optional[Sequence[ImageTile]] = None
    ) -> np.ndarray:
        """Join the current row-major tile list into one display image."""

        board = self.tiles if tiles is None else tiles
        if self.grid_size is None:
            raise ImageProcessingError("A grid size has not been selected")
        self._validate_tile_list(board, self.grid_size)

        rows = []
        for row in range(self.grid_size):
            start = row * self.grid_size
            row_tiles = board[start : start + self.grid_size]
            rows.append(cv2.hconcat([tile.image for tile in row_tiles]))
        return cv2.vconcat(rows)

    def process_image(
        self, file_path: Union[str, Path], grid_size: GridSize
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Run the complete load-to-scrambled-image pipeline.

        Returns:
            ``(original_image, transformed_image)`` as BGR NumPy arrays.  The
            master tile list is available as :attr:`tiles`.
        """

        selected_grid_size = self.parse_grid_size(grid_size)
        loaded_image = self.load_image(file_path)
        prepared_image = self.resize_and_pad(loaded_image, selected_grid_size)

        # Assign state only after loading/preparation succeeds.  A failed load
        # therefore cannot leave a half-reset puzzle round behind.
        new_tiles = self.slice_image(prepared_image, selected_grid_size)
        self.grid_size = selected_grid_size
        self.original_image = prepared_image.copy()
        self.tiles = new_tiles
        self.apply_random_transformations()
        self.transformed_image = self.reassemble_image()

        return self.original_image.copy(), self.transformed_image.copy()

    # ``prepare_puzzle`` reads naturally at the GUI call site while
    # ``process_image`` remains the conventional image-processing API name.
    prepare_puzzle = process_image

    def solved_image(self) -> np.ndarray:
        """Restore the master tile list and return the solved board image."""

        if self.original_image is None or self.grid_size is None:
            raise ImageProcessingError("No puzzle image has been processed")

        self.tiles = self.slice_image(self.original_image, self.grid_size)
        self.transformation_log = []
        self.transformed_image = self.original_image.copy()
        return self.transformed_image.copy()

    @property
    def incorrect_tile_count(self) -> int:
        """Number of tiles not currently in their solved state."""

        return sum(not tile.is_correct for tile in self.tiles)

    def _swap_tiles(
        self, board: List[ImageTile], first: ImageTile, second: ImageTile
    ) -> None:
        first_index = next(i for i, tile in enumerate(board) if tile is first)
        second_index = next(i for i, tile in enumerate(board) if tile is second)
        board[first_index], board[second_index] = (
            board[second_index],
            board[first_index],
        )
        self.transformation_log.append(
            Transformation("swap", (first.tile_id, second.tile_id))
        )

    def _rotate_tile(self, tile: ImageTile) -> None:
        angle = self.rng.choice((90, 180, 270))
        rotation_codes = {
            90: cv2.ROTATE_90_CLOCKWISE,
            180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE,
        }
        tile.image = cv2.rotate(tile.image, rotation_codes[angle])
        tile.rotation = angle
        self.transformation_log.append(
            Transformation("rotate", (tile.tile_id,), angle)
        )

    def _flip_tile(self, tile: ImageTile) -> None:
        direction = self.rng.choice(("horizontal", "vertical"))
        flip_code = 1 if direction == "horizontal" else 0
        tile.image = cv2.flip(tile.image, flip_code)
        tile.flip = direction
        self.transformation_log.append(
            Transformation("flip", (tile.tile_id,), direction)
        )

    @staticmethod
    def _refresh_positions(board: Sequence[ImageTile], grid_size: int) -> None:
        for index, tile in enumerate(board):
            tile.current_position = divmod(index, grid_size)

    @staticmethod
    def _validate_image_array(image: np.ndarray) -> None:
        if not isinstance(image, np.ndarray) or image.size == 0:
            raise ImageProcessingError("Image must be a non-empty NumPy array")
        if image.ndim != 3 or image.shape[2] != 3:
            raise ImageProcessingError("Image must contain three BGR colour channels")

    @staticmethod
    def _validate_tile_list(
        tiles: Sequence[ImageTile], grid_size: int
    ) -> None:
        expected_count = grid_size * grid_size
        if len(tiles) != expected_count:
            raise ImageProcessingError(
                f"Expected {expected_count} tiles, received {len(tiles)}"
            )
        if not all(isinstance(tile, ImageTile) for tile in tiles):
            raise ImageProcessingError("Tile list contains an invalid tile object")


__all__ = [
    "ImageProcessingError",
    "ImageProcessor",
    "ImageTile",
    "Transformation",
]
