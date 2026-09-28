import cv2


class Puzzle:
    def __init__(self, processor):
        self.processor = processor
        self.grid_size = processor.grid_size
        self.selected_position = None

    def get_tile_at(self, position):
        row, col = position
        index = row * self.grid_size + col
        return self.processor.tiles[index]

    def select(self, position):
        """Handle a left click. First click selects, a second click on a
        different tile swaps the two, a second click on the same tile
        deselects. Returns True if a swap happened, False otherwise."""
        if self.selected_position is None:
            self.selected_position = position
            return False
        if self.selected_position == position:
            self.selected_position = None
            return False

        self._swap(self.selected_position, position)
        self.selected_position = None
        return True

    def rotate(self, position):
        """Rotate the tile at `position` 90 degrees clockwise."""
        tile = self.get_tile_at(position)
        self._rotate_tile(tile)

    def flip(self, position):
        """Flip the tile at `position` horizontally."""
        tile = self.get_tile_at(position)
        self._flip_tile_horizontal(tile)

    @staticmethod
    def _rotate_tile(tile):
        tile.image = cv2.rotate(tile.image, cv2.ROTATE_90_CLOCKWISE)
        if tile.flip is None:
            tile.rotation = (tile.rotation + 90) % 360
        else:
            tile.rotation = (tile.rotation - 90) % 360

    @staticmethod
    def _flip_tile_horizontal(tile):
        tile.image = cv2.flip(tile.image, 1)
        if tile.flip is None:
            tile.flip = "horizontal"
        elif tile.flip == "horizontal":
            tile.flip = None
        else:
            tile.flip = None
            tile.rotation = (tile.rotation + 180) % 360

    def _swap(self, position_a, position_b):
        grid_size = self.grid_size
        index_a = position_a[0] * grid_size + position_a[1]
        index_b = position_b[0] * grid_size + position_b[1]
        tiles = self.processor.tiles

        tile_a = tiles[index_a]
        tile_b = tiles[index_b]

        tile_a.current_position, tile_b.current_position = (
            tile_b.current_position,
            tile_a.current_position,
        )
        tiles[index_a], tiles[index_b] = tile_b, tile_a
