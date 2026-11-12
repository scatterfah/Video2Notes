"""
Removes duplicate and near-duplicate screenshots.

Idea
----
1. Every screenshot is turned into an "ink map": only the writing (or drawing),
   without the board background.
2. Screenshots are grouped into "boards". A new board starts when the teacher
   erases things, changes the slide, or the board is blank.
3. Inside one board the writing only grows. We keep a screenshot only when it adds
   a meaningful amount of new writing, and we always keep the last (most complete)
   one. How much counts as "meaningful" depends on the detail level.

Removed screenshots are not deleted. They are moved into a "skipped" folder.
"""

from pathlib import Path
import shutil

import cv2
import numpy as np


# ============================================================
# SETTINGS
# ============================================================

# How much NEW writing a screenshot must add (as a fraction of the finished
# board) to be kept as its own stage. None = only the finished board.
DETAIL_LEVELS = {
    "final": None,      # one screenshot per board (the finished board)
    "balanced": 0.25,   # about up to 4 stages per board
    "detailed": 0.10,   # about up to 10 stages per board
}

DEFAULT_DETAIL = "balanced"

# Size used for comparing screenshots (saved screenshots are NOT changed)
COMPARE_WIDTH = 960

# A pixel counts as writing if it differs this much from the board background
INK_CONTRAST = 40

# A screenshot with less writing than this (fraction of all pixels) and an
# almost uniform background counts as a blank board
BLANK_INK = 0.0005
BLANK_STD = 18

# Writing that moved by a few pixels still counts as the same writing
TOLERANCE_KERNEL = 7

# If more than this share of the previous writing disappeared, the board was
# erased or changed, so a new board starts
ERASE_LIMIT = 0.12

# Less than this share of changed writing means "nothing really changed"
DUPLICATE_LIMIT = 0.03

# Ignore changes smaller than this many pixels (video noise)
MIN_PIXELS = 150

SKIPPED_FOLDER = "skipped"


# ============================================================
# INK MAP
# ============================================================

def load_ink_map(path):
    """Returns (ink_mask, is_blank_background) for one screenshot."""

    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

    if image is None:
        return None, True

    height, width = image.shape
    new_height = max(1, int(height * COMPARE_WIDTH / width))

    small = cv2.resize(image, (COMPARE_WIDTH, new_height), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (3, 3), 0)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))

    if np.median(small) >= 127:
        # Light board, dark writing
        background = cv2.morphologyEx(small, cv2.MORPH_CLOSE, kernel)
        difference = cv2.subtract(background, small)
    else:
        # Dark board, light writing
        background = cv2.morphologyEx(small, cv2.MORPH_OPEN, kernel)
        difference = cv2.subtract(small, background)

    _, mask = cv2.threshold(difference, INK_CONTRAST, 255, cv2.THRESH_BINARY)

    uniform = float(np.std(small)) < BLANK_STD

    return mask, uniform


def ink_amount(mask):
    return cv2.countNonZero(mask)


def new_ink(reference, candidate):
    """How much writing is in `candidate` that is not in `reference`."""

    grow = cv2.getStructuringElement(
        cv2.MORPH_RECT, (TOLERANCE_KERNEL, TOLERANCE_KERNEL)
    )
    reference_wide = cv2.dilate(reference, grow)

    extra = cv2.bitwise_and(candidate, cv2.bitwise_not(reference_wide))
    return cv2.countNonZero(extra)


# ============================================================
# MAIN FUNCTION
# ============================================================

def remove_redundant_screenshots(output_dir, detail=DEFAULT_DETAIL, log=print):
    """
    Keeps the meaningful screenshots in output_dir and moves the rest into
    output_dir/skipped. Returns the number of screenshots kept.
    """

    output_dir = Path(output_dir)
    images = sorted(output_dir.glob("*.jpg"))

    if len(images) < 2:
        return len(images)

    if detail not in DETAIL_LEVELS:
        detail = DEFAULT_DETAIL

    step = DETAIL_LEVELS[detail]

    # ---- 1. ink map of every screenshot ----
    masks = []
    blank = []

    for path in images:
        mask, uniform = load_ink_map(path)

        if mask is None:
            masks.append(None)
            blank.append(True)
            continue

        pixels = mask.size
        masks.append(mask)
        blank.append(uniform and ink_amount(mask) < pixels * BLANK_INK)

    # If everything looks blank, the ink detection is not suitable for this
    # video (photos, animations ...). Do nothing instead of deleting things.
    if all(blank):
        log("Duplicate removal skipped: no writing could be detected.")
        return len(images)

    # ---- 2. split into boards ----
    boards = []
    current = []

    for index, mask in enumerate(masks):

        if blank[index]:
            if current:
                boards.append(current)
                current = []
            continue

        if not current:
            current = [index]
            continue

        previous = masks[current[-1]]
        base = max(ink_amount(previous), MIN_PIXELS)
        removed = new_ink(mask, previous)  # writing that is gone now

        if removed > ERASE_LIMIT * base and removed > MIN_PIXELS:
            boards.append(current)
            current = [index]
        else:
            current.append(index)

    if current:
        boards.append(current)

    # ---- 3. choose the screenshots to keep inside each board ----
    keep = set()

    for board in boards:

        last_index = board[-1]
        final_ink = max(ink_amount(masks[last_index]), MIN_PIXELS)

        kept_here = []

        if step is not None:
            kept_mask = None

            for index in board[:-1]:
                mask = masks[index]

                if kept_mask is None:
                    added = ink_amount(mask)
                else:
                    added = new_ink(kept_mask, mask)

                if added >= step * final_ink and added > MIN_PIXELS:
                    kept_here.append(index)
                    kept_mask = mask

            last_kept_mask = masks[kept_here[-1]] if kept_here else None
        else:
            last_kept_mask = None

        # Always keep the final, most complete screenshot of the board.
        # If it only adds a little to the last kept one, it replaces that one.
        if kept_here:
            added_by_final = new_ink(last_kept_mask, masks[last_index])

            if added_by_final < max(step * final_ink, MIN_PIXELS):
                kept_here.pop()

        kept_here.append(last_index)
        keep.update(kept_here)

    # ---- 4. move everything else into "skipped" ----
    skipped_dir = output_dir / SKIPPED_FOLDER
    skipped_dir.mkdir(exist_ok=True)

    moved = 0

    for index, path in enumerate(images):
        if index not in keep:
            shutil.move(str(path), str(skipped_dir / path.name))
            moved += 1

    log(
        f"Duplicate removal: kept {len(keep)} of {len(images)} screenshots "
        f"({moved} moved to the '{SKIPPED_FOLDER}' folder)."
    )

    return len(keep)
