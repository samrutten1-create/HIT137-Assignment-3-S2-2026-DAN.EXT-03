# HIT137-Assignment-3-S2-2026-DAN.EXT-03

A desktop image puzzle for HIT137 Group Assignment 3, Semester 2, 2026.
Choose an image and a 3x3, 4x4, or 5x5 grid, then restore the scrambled picture
by swapping, rotating, and flipping tiles. The application tracks moves and
incorrect tiles, provides up to three hints per image, and detects completion.

## Setup
From the project folder, install the libraries:
```powershell
python -m pip install opencv-python numpy Pillow
```
- OpenCV (`cv2`) loads and transforms images.
- NumPy (`numpy`) stores and combines image pixels.
- Pillow (`PIL`) converts images for display in Tkinter.
- Tkinter (`tkinter`) provides the desktop interface. It is included in standard
  Windows Python installations when the Tcl/Tk component is installed.

## Run the application

Run this command from the project folder:

```powershell
python main.py
```

The launcher imports the application modules and opens the GUI last.
To open the GUI through its individual module option, use:

```powershell
python main.py main_window
```

Choose the grid size before clicking **Load Image**. The default is 3x3.
JPG/JPEG, PNG, and BMP images are supported. The image is resized with its aspect
ratio preserved and padded into an evenly divisible square grid. The original
appears on the left; the playable puzzle appears on the right.

## Controls

Use these mouse controls on the right-hand image:

| Control | Action |
| --- | --- |
| Left click a tile | Select it and show a coloured border. |
| Left click a different tile | Swap it with the selected tile and clear selection. |
| Left click the selected tile again | Deselect it. |
| Right click a tile | Rotate it 90 degrees clockwise. |
| Shift + left click a tile | Flip it horizontally. |
| Hint button | Circle an incorrect tile on the right and its home on the left. |
| Solve button | Restore the original image and reset the move/incorrect counters. |

Each swap, rotation, or flip counts as one move. Selecting or deselecting a tile
does not count. A green tick marks a tile only when its position and orientation
are correct.

There are three hints per image. Hint circles disappear after the next move,
and the button is disabled once all three hints have been used. Completion and
Solve both lock further tile input. Load another image to start a new round with
fresh counters, selection, and hints.

## Project structure

| File | Responsibility |
| --- | --- |
| `main.py` | Launch the GUI or check module imports. |
| `gui/main_window.py` | Build the Tkinter window, display images, and bind controls. |
| `image_processing/image_processor.py` | Load, resize, pad, split, scramble, reassemble, and restore images; store tile state. |
| `puzzle/puzzle.py` | Select, swap, rotate, and flip the current tiles. |
| `puzzle/actions.py` | Define the common action base class and its three subclasses. |
| `game/game_manager.py` | Coordinate actions, scoring, hints, overlays, solving, and completion. |
| `tests/test_actions.py` | Test action behavior and its effect on the controller and GUI. |
| `tests/test_image_processor.py` | Test image loading, preparation, scrambling, and restoration. |

## Object-oriented design

- **Encapsulation:** each class groups related state and behavior. For example,
  `GameManager` manages the round's moves and hints, while `ImageProcessor`
  manages image preparation and tile data.
- **Constructors:** `__init__` methods set up objects and their starting state.
  `ImageTile` is a dataclass, which generates a constructor for its tile fields.
- **Methods:** classes provide operations such as `Puzzle.rotate()` and
  `GameManager.show_hint()`.
- **Class interaction:** the GUI creates a game manager, which coordinates a
  puzzle and its action objects using the image processor's tiles.
- **Inheritance:** `SelectAction`, `RotateAction`, and `FlipAction` inherit from
  `PuzzleAction`, including its constructor and reference to the puzzle.
- **Polymorphism:** each action overrides `apply(position)`. The game manager
  calls the same method through one shared handler, and the selected action
  decides what happens. It returns `True` for a completed move and `False` for
  selection or deselection, allowing the controller to count moves correctly.

## Import checks and tests

These commands check imports without opening the GUI:

```powershell
python -B main.py --check
python -B main.py actions --check
python -B main.py image_processor --check
```

The launcher accepts `actions`, `puzzle`, `image_processor`, `game_manager`, and
`main_window`. Modules without their own `main()` function are imported and
skipped for execution. Use `python main.py --help` to see the options.

Run the automated tests from the project folder:

```powershell
python -B -m unittest discover -s tests -v
```

The suite contains 30 tests using Python's built-in `unittest` framework, so no
additional testing library is required. Some tests check several inputs using
subtests, including all three grid sizes.

| Test file | Coverage |
| --- | --- |
| `tests/test_actions.py` | Selection, deselection, swaps, rotations, flips, mixed orientation changes, move counting, correctness ticks, hints and their limit, completion, Solve, cancelled/invalid loads, and round resets. Also checks tile edges and overlay alignment against Tkinter's actual image bounds, including the 399x399 board used for 3x3 puzzles. |
| `tests/test_image_processor.py` | JPG/JPEG, PNG, and BMP loading; filenames with non-ASCII characters; grayscale and transparent images; invalid files and grid sizes; aspect ratio and padding; tile ordering and independent image copies; repeatable scrambling with no repeated tile targets; restoration; and preserving the board after a failed load. |

To run just one test file:

```powershell
python -B -m unittest discover -s tests -p test_actions.py -v
python -B -m unittest discover -s tests -p test_image_processor.py -v
```

The GUI tests create withdrawn Tkinter windows and mock file dialogs and
completion/error message boxes. They require a working Tkinter display; if
one is unavailable, those tests are reported as skipped. Image-processing and
puzzle-action tests can run without a display. Test images are generated in
memory or temporary folders, which are cleaned up automatically.

Import checks only verify that modules load. Automated tests check model state,
controller behavior, and canvas contents; manually check actual mouse controls,
window resizing, and visual appearance before submission.
