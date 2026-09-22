"""Run the image puzzle application or an individual module."""
import argparse
import importlib
# Run the GUI last because its event loop waits until the window is closed.
MODULES = {
    "tile": "puzzle.tile",
    "puzzle": "puzzle.puzzle",
    "image_processor": "image_processing.image_processor",
    "game_manager": "game.game_manager",
    "main_window": "gui.main_window",
}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "module", nargs="?", default="all", choices=["all", *MODULES],
        help="Module to run (default: all).",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check imports only, without calling main() or opening the GUI.",
    )
    args = parser.parse_args(argv)
    selected = MODULES if args.module == "all" else {args.module: MODULES[args.module]}
    for name, module_path in selected.items():
        module = importlib.import_module(module_path)
        print(f"Loaded {name}", flush=True)
        if args.check:
            continue

        entry_point = getattr(module, "main", None)
        if callable(entry_point):
            entry_point()
        else:
            print(f"  No main() yet; skipping {name}.", flush=True)
if __name__ == "__main__":
    main()
