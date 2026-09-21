import tkinter as tk

def main_window():
    # main window
    root = tk.Tk()
    root.title("HIT137 Assignment 3 - Image Puzzle")
    
    # Set window dimensions, this is to accommodate for 2 400x400 photos side by side?
    root.geometry("1200x600")

    # frame for top menu
    frame = tk.Frame(root)
    frame.pack(anchor="nw", padx=5, pady=5)

    # "Grid Size:" label
    label = tk.Label(frame, text="Grid Size:", font=("Segoe UI", 12))
    label.pack(side=tk.LEFT, padx=5)

    options = ["3x3", "4x4", "5x5"]
    selected_size = tk.StringVar(root)
    
    # set default value to 3x3
    selected_size.set(options[0]) 
    
    dropdown = tk.OptionMenu(frame, selected_size, *options)
    
    # configure the dropdown button
    dropdown.config(width=4, font=("Segoe UI", 12))
     
    dropdown.pack(side=tk.LEFT)

    root.mainloop()

if __name__ == "__main__":
    main_window()
