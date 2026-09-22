import tkinter as tk
from tkinter import filedialog

class PuzzleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("HIT137 Assignment 3 - Image Puzzle")
        self.root.geometry("1000x600")
        
        self.setup_ui()

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


def main():
    """Open the puzzle window, directly or through the project launcher."""
    main_window = tk.Tk()
    app = PuzzleGUI(main_window)
    main_window.mainloop()


if __name__ == "__main__":
    main()
