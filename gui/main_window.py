import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox

import cv2
from PIL import Image, ImageTk

from image_processing.image_processor import ImageProcessingError, ImageProcessor

class PuzzleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HIT137 Assignment 3 - Image Puzzle")
        self.root.geometry("1000x600")

        self.image_processor = ImageProcessor(max_size=(400, 400))
        self.original_photo = None
        self.game_photo = None
        
        self.setup_ui()
        self.hint_button.config(state=tk.DISABLED)
        self.solve_button.config(command=self.solve_puzzle, state=tk.DISABLED)

    def setup_ui(self):
        # Top frame for controls
        self.menu_frame = tk.Frame(self.root)
        self.menu_frame.pack(anchor="nw", fill=tk.X, padx=5, pady=5)

        # Dropdown for grid size selection
        self.grid_label = tk.Label(self.menu_frame, text="Grid Size:", font=("Arial", 12))
        self.grid_label.pack(side=tk.LEFT, padx=5)
        
        self.grid_options = ["3x3", "4x4", "5x5"]
        self.selected_size = tk.StringVar(self.root)
        self.selected_size.set(self.grid_options[0]) 
        
        self.size_dropdown = tk.OptionMenu(self.menu_frame, self.selected_size, *self.grid_options)
        self.size_dropdown.config(width=4, font=("Arial", 12))
        self.size_dropdown.pack(side=tk.LEFT, padx=(0, 10))

        # Button to trigger image loading
        self.load_button = tk.Button(self.menu_frame, text="Load Image", font=("Arial", 12), command=self.load_image)
        self.load_button.pack(side=tk.LEFT, padx=5)

        # Game control buttons
        self.hint_button = tk.Button(self.menu_frame, text="Hint (3)", font=("Arial", 12))
        self.hint_button.pack(side=tk.LEFT, padx=5)

        self.solve_button = tk.Button(self.menu_frame, text="Solve", font=("Arial", 12))
        self.solve_button.pack(side=tk.LEFT, padx=5)

        # Moves and tile status label
        self.score_label = tk.Label(self.menu_frame, text="Moves: 0 | Incorrect: 0", font=("Arial", 12))
        self.score_label.pack(side=tk.RIGHT, padx=20)

        # Frame for displaying images
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=20)

        # Canvas for original image
        self.canvas_orig = tk.Canvas(self.canvas_frame, width=400, height=400, bg="lightgray")
        self.canvas_orig.pack(side=tk.LEFT, padx=40)

        # Canvas for interactive puzzle board
        self.canvas_game = tk.Canvas(self.canvas_frame, width=400, height=400, bg="darkgray")
        self.canvas_game.pack(side=tk.LEFT, padx=10)

    def load_image(self):
        # Open file dialog to select image file
        file_path = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
        )
        if file_path:
            print("Image Loaded") # This is just placeholder code until it is passed onto image manipulation

            try:
                original_image, transformed_image = self.image_processor.process_image(
                    file_path,
                    self.selected_size.get(),
                )
            except ImageProcessingError as error:
                messagebox.showerror("Image Error", str(error))
                return

            self.original_photo = self.display_image(
                self.canvas_orig,
                original_image,
            )
            self.game_photo = self.display_image(
                self.canvas_game,
                transformed_image,
            )
            self.draw_game_grid(transformed_image)

            self.score_label.config(
                text=(
                    "Moves: 0 | Incorrect: "
                    f"{self.image_processor.incorrect_tile_count}"
                )
            )
            self.hint_button.config(text="Hint (3)", state=tk.NORMAL)
            self.solve_button.config(state=tk.NORMAL)

    def display_image(self, canvas, image):
        """Convert an OpenCV image and display it in the centre of a canvas."""
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        photo = ImageTk.PhotoImage(Image.fromarray(rgb_image))

        canvas.delete("all")
        canvas_width = int(canvas.cget("width"))
        canvas_height = int(canvas.cget("height"))
        canvas.create_image(
            canvas_width // 2,
            canvas_height // 2,
            image=photo,
            anchor=tk.CENTER,
        )
        return photo

    def draw_game_grid(self, image):
        """Draw faint tile boundaries over the transformed image."""
        grid_size = self.image_processor.grid_size
        if grid_size is None:
            return

        image_height, image_width = image.shape[:2]
        canvas_width = int(self.canvas_game.cget("width"))
        canvas_height = int(self.canvas_game.cget("height"))
        left = (canvas_width - image_width) // 2
        top = (canvas_height - image_height) // 2
        tile_width = image_width / grid_size
        tile_height = image_height / grid_size

        for boundary in range(1, grid_size):
            x = left + boundary * tile_width
            y = top + boundary * tile_height
            self.canvas_game.create_line(
                x,
                top,
                x,
                top + image_height,
                fill="#ff0000",
            )
            self.canvas_game.create_line(
                left,
                y,
                left + image_width,
                y,
                fill="#ff0000",
            )

    def solve_puzzle(self):
        """Display the restored image when the existing Solve button is used."""
        if self.image_processor.original_image is None:
            return

        solved_image = self.image_processor.solved_image()
        self.game_photo = self.display_image(self.canvas_game, solved_image)
        self.draw_game_grid(solved_image)
        self.score_label.config(text="Moves: 0 | Incorrect: 0")
        self.hint_button.config(state=tk.DISABLED)
        self.solve_button.config(state=tk.DISABLED)


def main():
    """Open the puzzle window, directly or through the project launcher."""
    main_window = tk.Tk()
    app = PuzzleGUI(main_window)
    main_window.mainloop()


if __name__ == "__main__":
    main()
