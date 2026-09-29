import tkinter as tk
from puzzle.puzzle import Puzzle

class GameManager:
    """ 
    Controller class responsible for game logic and visual validation
    """
    def __init__(self, gui):
        """
        Start the game controller and check for correct tiles
        """
        self.gui = gui
        self.processor = gui.image_processor
        
        # Start puzzle module
        self.puzzle = Puzzle(self.processor)
        
        # Initial check for any tiles that started in the correct position
        self.mark_correct()

    def mark_correct(self):
        """
        Draw a green tick on any tile that is in its exact home position
        """
        self.gui.canvas_game.delete("tick")
        
        if self.processor.transformed_image is None or not self.processor.tiles:
            return
            
        img_h, img_w = self.processor.transformed_image.shape[:2]
        
        # Get grid size from puzzle module
        grid_size = self.puzzle.grid_size
        tile_w = img_w // grid_size
        tile_h = img_h // grid_size

        # Calculate offsets so the ticks align with the image
        canvas_w = int(self.gui.canvas_game.cget("width"))
        canvas_h = int(self.gui.canvas_game.cget("height"))
        left_offset = (canvas_w - img_w) // 2
        top_offset = (canvas_h - img_h) // 2
        
        for tile in self.processor.tiles:
            if tile.is_correct:
                row, col = tile.current_position
                x = left_offset + (col * tile_w) + 20
                y = top_offset + (row * tile_h) + 20
                
                self.gui.canvas_game.create_text(
                    x, y, text="✔", fill="#00ff00", font=("Arial", 16, "bold"), tags="tick"
                )

