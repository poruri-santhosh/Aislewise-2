"""Safely organize root-level project scripts and generated artifacts."""

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DESTINATIONS = {
    "scripts": (
        "scenario_a_*.py",
        "scenario_b_*.py",
        "scenario_c_*.py",
        "deep_investigation_suite.py",
    ),
    "reports": (),
    "visuals": (),
}
REPORT_EXTENSIONS = {".txt", ".json", ".csv"}
VISUAL_EXTENSIONS = {".png", ".jpg"}
PROTECTED_REPORT_FILES = {
    "requirements.txt",
    "requirements-analysis.txt",
    "requirements-dev.txt",
    "vercel.json",
}
DESTINATION_DIRECTORIES = ("scripts", "reports", "visuals")


def plan_moves():
    """Return root-level file moves without changing the filesystem."""
    moves = []
    for pattern in DESTINATIONS["scripts"]:
        moves.extend(
            (path, PROJECT_ROOT / "scripts" / path.name)
            for path in PROJECT_ROOT.glob(pattern)
            if path.is_file()
        )

    for path in PROJECT_ROOT.iterdir():
        if not path.is_file() or path.name.lower() in PROTECTED_REPORT_FILES:
            continue
        suffix = path.suffix.lower()
        if suffix in REPORT_EXTENSIONS:
            destination = PROJECT_ROOT / "reports" / path.name
        elif suffix in VISUAL_EXTENSIONS:
            destination = PROJECT_ROOT / "visuals" / path.name
        else:
            continue
        moves.append((path, destination))
    return moves


def organize(apply_changes=False):
    if apply_changes:
        for directory in DESTINATION_DIRECTORIES:
            (PROJECT_ROOT / directory).mkdir(parents=True, exist_ok=True)

    moves = plan_moves()
    if not moves:
        print("No matching root-level files to organize.")
        return

    for source, destination in moves:
        if destination.exists():
            print(f"Skipping existing destination: {destination.relative_to(PROJECT_ROOT)}")
            continue
        if not apply_changes:
            print(
                f"Would move {source.relative_to(PROJECT_ROOT)} "
                f"-> {destination.relative_to(PROJECT_ROOT)}"
            )
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        print(
            f"Moved {source.relative_to(PROJECT_ROOT)} "
            f"-> {destination.relative_to(PROJECT_ROOT)}"
        )

    if not apply_changes:
        print("Preview only; rerun with --apply to move these files.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the listed moves (default is a non-destructive preview)",
    )
    args = parser.parse_args()
    organize(apply_changes=args.apply)


if __name__ == "__main__":
    main()
