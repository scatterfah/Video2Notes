from pathlib import Path
import os
import shutil
import sys
import subprocess

import cv2
import yt_dlp
from PIL import Image
from tqdm import tqdm

from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# ============================================================
# PROJECT SETTINGS
# ============================================================

# In the packaged .exe, ffmpeg.exe and deno.exe are bundled inside it.
# Put that folder first in PATH so the program (and yt-dlp) can find them.
if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", str(Path(sys.executable).parent))
    os.environ["PATH"] = bundle_dir + os.pathsep + os.environ.get("PATH", "")

# As a normal script: save next to the code.
# As a packaged .exe: save in Documents/WhiteboardExtractor.
if getattr(sys, "frozen", False):
    BASE_DIR = Path.home() / "Documents" / "WhiteboardExtractor"
else:
    BASE_DIR = Path(__file__).resolve().parent

BASE_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_DIR = BASE_DIR / "videos"
OUTPUT_DIR = BASE_DIR / "extracted_notes"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Analyze one frame every 0.5 seconds
SAMPLE_INTERVAL = 0.5

# Wait this long after writing activity stops before saving
QUIET_SECONDS = 2.0

# Minimum amount of screen change required
CHANGE_THRESHOLD = 0.001

# Minimum movement/activity required
ACTIVITY_THRESHOLD = 0.00025

# Resize width for detection only (saved images keep original resolution)
DETECTION_WIDTH = 960

# Image quality for saved screenshots
JPEG_QUALITY = 95

# Crop applied ONLY to the PDF pages (fraction of the image, 0 = no crop).
# Example: CROP_LEFT = 0.05 removes 5% from the left side.
CROP_LEFT = 0
CROP_RIGHT = 0
CROP_TOP = 0
CROP_BOTTOM = 0

# Highest resolution allowed (1080 is plenty for handwriting)
MAX_HEIGHT = 1080

# Automatic quality choice, in this order of importance:
#   1. highest resolution (up to MAX_HEIGHT)
#   2. H.264 codec (OpenCV can read it on every computer)
#   3. highest bitrate (sharper thin handwriting)
VIDEO_FORMAT = (
    f"bestvideo[height<={MAX_HEIGHT}]/"
    f"best[height<={MAX_HEIGHT}]/"
    "best"
)
FORMAT_SORT = ["res", "vcodec:h264", "br"]


# ============================================================
# 1. DOWNLOAD YOUTUBE VIDEO
# ============================================================

def log(message):
    # Safe printing: works with the progress bar, and when there is no console
    if sys.stdout is not None:
        tqdm.write(message)


def download_video(url, on_progress=None):

    print("\nDownloading video...")

    def download_hook(d):
        if on_progress is None or d.get("status") != "downloading":
            return

        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        done = d.get("downloaded_bytes", 0)

        if total:
            percent = done / total * 100
        elif d.get("fragment_count"):
            percent = d.get("fragment_index", 0) / d["fragment_count"] * 100
        else:
            return

        on_progress("Downloading", min(percent, 100))

    ydl_options = {
        "format": VIDEO_FORMAT,
        "format_sort": FORMAT_SORT,
        # Resolution is part of the name, so an old 360p file is never reused
        "outtmpl": str(VIDEO_DIR / "%(id)s_%(height)sp.%(ext)s"),
        "noplaylist": True,
        "quiet": on_progress is not None,
        "no_warnings": on_progress is not None,
        "noprogress": on_progress is not None,
        "progress_hooks": [download_hook],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:

            info = ydl.extract_info(url, download=True)

            video_id = info.get("id")

            if not video_id:
                raise RuntimeError("Could not identify the downloaded video.")

            video_path = Path(ydl.prepare_filename(info))

            if not video_path.exists():
                # Handle cases where the final extension differs
                candidates = [
                    file for file in VIDEO_DIR.glob(f"{video_id}.*")
                    if file.suffix.lower() in {
                        ".mp4", ".mkv", ".webm", ".mov", ".avi"
                    }
                ]

                if not candidates:
                    raise FileNotFoundError(
                        "Downloaded video file could not be found."
                    )

                video_path = max(candidates, key=lambda file: file.stat().st_size)

            print(f"\nDownload complete: {video_path.name}")

            return video_path

    except Exception as error:
        raise RuntimeError(f"Video download failed: {error}") from error


# ============================================================
# 2. MAKE SURE OPENCV CAN READ THE VIDEO
# ============================================================

def can_read_video(path):
    cap = cv2.VideoCapture(str(path))
    ok = False

    if cap.isOpened():
        ok, _ = cap.read()

    cap.release()
    return ok


def ensure_readable(video_path):
    """
    Some videos (for example AV1) cannot be decoded by OpenCV.
    If that happens, convert a copy with FFmpeg and use the copy.
    """

    if can_read_video(video_path):
        return video_path

    print("\nOpenCV cannot decode this video (probably AV1).")
    print("Converting a copy with FFmpeg. This may take a minute...")

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg is not installed, so the video cannot be converted. "
            "Install FFmpeg and try again."
        )

    converted = video_path.with_name(video_path.stem + "_converted.mp4")

    # Reuse an earlier conversion if it already works
    if converted.exists() and can_read_video(converted):
        print(f"Using existing converted file: {converted.name}")
        return converted

    # Try the best encoder first, then simpler ones
    encoders = [
        ["-c:v", "libx264", "-crf", "18", "-preset", "fast"],
        ["-c:v", "libopenh264", "-b:v", "8M"],
        ["-c:v", "mpeg4", "-q:v", "2"],
    ]

    for encoder in encoders:
        command = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(video_path),
            *encoder,
            "-an",
            str(converted),
        ]

        # On Windows, don't flash a black console window
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(command, creationflags=flags)

        if result.returncode == 0 and converted.exists() and can_read_video(converted):
            print(f"Conversion complete: {converted.name}")
            return converted

    raise RuntimeError("Could not convert the video to a readable format.")


# ============================================================
# 3. SAVE WHITEBOARD SCREENSHOT
# ============================================================

def save_frame(frame, timestamp, count, output_dir):

    minutes = int(timestamp // 60)
    seconds = int(timestamp % 60)

    filename = f"{count:04d}_{minutes:02d}-{seconds:02d}.jpg"

    image_path = output_dir / filename

    success = cv2.imwrite(
        str(image_path),
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    )

    if success:
        log(f"Saved screenshot: {filename}")
        return True

    log(f"Could not save screenshot: {filename}")
    return False


# ============================================================
# 4. DETECT WHITEBOARD CHANGES
# ============================================================

def detect_writing(video_path, output_dir, on_progress=None):

    print("\nAnalyzing whiteboard changes...")

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError("Could not open the downloaded video.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    if fps <= 0 or total_frames <= 0:
        cap.release()
        raise RuntimeError("Invalid video information.")

    duration = total_frames / fps

    print(f"Video duration: {duration / 60:.2f} minutes")
    print(f"FPS: {fps:.2f}")

    frame_interval = max(1, round(fps * SAMPLE_INTERVAL))

    previous_gray = None
    baseline_gray = None

    pending_frame = None
    last_stable_frame = None

    last_activity = 0.0

    saved_count = 0
    frame_number = 0

    # Progress bar that fills from 0% to 100% on a single line
    progress_bar = tqdm(
        total=int(total_frames),
        desc="Analyzing",
        disable=on_progress is not None,
        bar_format="{desc}: {percentage:3.0f}%|{bar:30}| {elapsed} < {remaining}  {postfix}",
    )

    try:

        while True:

            success, frame = cap.read()

            if not success:
                break

            frame_number += 1

            # Analyze only selected frames
            if frame_number % frame_interval != 0:
                continue

            timestamp = frame_number / fps

            progress_bar.update(frame_interval)
            progress_bar.set_postfix(screenshots=saved_count)

            if on_progress is not None:
                on_progress("Analyzing", min(frame_number / total_frames * 100, 100))

            # Resize for faster detection
            height, width = frame.shape[:2]

            new_height = int(height * DETECTION_WIDTH / width)

            small_frame = cv2.resize(
                frame,
                (DETECTION_WIDTH, new_height)
            )

            gray = cv2.cvtColor(
                small_frame,
                cv2.COLOR_BGR2GRAY
            )

            gray = cv2.GaussianBlur(
                gray,
                (5, 5),
                0
            )

            # First analyzed frame
            if previous_gray is None:

                previous_gray = gray.copy()
                baseline_gray = gray.copy()

                saved_count += 1

                save_frame(
                    frame,
                    timestamp,
                    saved_count,
                    output_dir
                )

                log("Initial whiteboard screenshot saved.")

                continue

            # Detect movement between consecutive analyzed frames
            activity_diff = cv2.absdiff(
                previous_gray,
                gray
            )

            _, activity_mask = cv2.threshold(
                activity_diff,
                20,
                255,
                cv2.THRESH_BINARY
            )

            activity_ratio = (
                cv2.countNonZero(activity_mask)
                / activity_mask.size
            )

            # Detect content changes compared with the last saved board
            content_diff = cv2.absdiff(
                baseline_gray,
                gray
            )

            _, content_mask = cv2.threshold(
                content_diff,
                20,
                255,
                cv2.THRESH_BINARY
            )

            content_ratio = (
                cv2.countNonZero(content_mask)
                / content_mask.size
            )

            # Update activity timer when meaningful movement is detected
            if activity_ratio > ACTIVITY_THRESHOLD:
                last_activity = timestamp

            # A meaningful board change has occurred
            if content_ratio > CHANGE_THRESHOLD:

                if activity_ratio > ACTIVITY_THRESHOLD:
                    pending_frame = frame.copy()

                elif pending_frame is None:
                    pending_frame = frame.copy()

            # Keep the latest frame as a possible stable screenshot
            if pending_frame is not None:
                last_stable_frame = frame.copy()

            # Save after writing activity has stopped
            if (
                pending_frame is not None
                and timestamp - last_activity >= QUIET_SECONDS
            ):

                saved_count += 1

                save_frame(
                    last_stable_frame,
                    timestamp,
                    saved_count,
                    output_dir
                )

                # Use the current screen as the new comparison baseline
                baseline_gray = gray.copy()

                pending_frame = None
                last_stable_frame = None

            previous_gray = gray.copy()

        # No frame could be read at all
        if frame_number == 0:
            raise RuntimeError(
                "No frames could be read from the video. "
                "The video format is probably not supported."
            )

        # Save any remaining board change at the end of the video
        if pending_frame is not None and last_stable_frame is not None:

            saved_count += 1

            save_frame(
                last_stable_frame,
                duration,
                saved_count,
                output_dir
            )

    finally:
        if on_progress is not None:
            on_progress("Analyzing", 100)

        # Fill the bar to 100% and close it
        progress_bar.n = progress_bar.total
        progress_bar.set_postfix(screenshots=saved_count)
        progress_bar.refresh()
        progress_bar.close()
        cap.release()

    print("\nWhiteboard analysis complete.")
    print(f"Total screenshots saved: {saved_count}")

    return saved_count


# ============================================================
# 5. CREATE PDF FROM SCREENSHOTS
# ============================================================

def create_pdf(output_dir):

    print("\nCreating PDF...")

    images = sorted(output_dir.glob("*.jpg"))

    if not images:
        print("No images found. PDF not created.")
        return None

    pdf_path = output_dir / "Whiteboard_Notes.pdf"
    pdf = canvas.Canvas(str(pdf_path))

    page_width = 842  # same width as A4 landscape

    use_crop = any([CROP_LEFT, CROP_RIGHT, CROP_TOP, CROP_BOTTOM])

    for index, image_path in enumerate(images, start=1):

        if use_crop:
            frame = cv2.imread(str(image_path))
            h, w = frame.shape[:2]

            x1 = int(w * CROP_LEFT)
            x2 = int(w * (1 - CROP_RIGHT))
            y1 = int(h * CROP_TOP)
            y2 = int(h * (1 - CROP_BOTTOM))
            frame = frame[y1:y2, x1:x2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = ImageReader(Image.fromarray(rgb))
        else:
            # No crop: embed the JPEG directly, no quality loss
            image = ImageReader(str(image_path))

        image_width, image_height = image.getSize()

        # Page has exactly the same shape as the screenshot
        page_height = page_width * image_height / image_width

        pdf.setPageSize((page_width, page_height))
        pdf.drawImage(image, 0, 0, width=page_width, height=page_height)
        pdf.showPage()

        print(f"Added page {index}: {image_path.name}")

    pdf.save()

    print("\nPDF successfully created!")
    print("Location:", pdf_path)
    print("Total pages:", len(images))

    return pdf_path


# ============================================================
# 6. MAIN PROGRAM
# ============================================================

def process_video(url, on_progress=None, on_status=None):
    """
    Full pipeline: download -> analyze -> PDF.
    Used by both the terminal version and the window (GUI) version.

    on_progress(stage, percent) is called while downloading/analyzing.
    on_status(text) is called with short messages for the user.
    Returns the path of the finished PDF.
    """

    def status(message):
        if on_status is not None:
            on_status(message)

    # Step 1: Download video
    status("Downloading video...")
    video_path = download_video(url, on_progress)

    # Output folder is named after the ORIGINAL video id
    video_output = OUTPUT_DIR / video_path.stem
    video_output.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput folder: {video_output}")

    # Remove results of earlier runs so they don't mix into this PDF
    for old_file in list(video_output.glob("*.jpg")) + list(video_output.glob("*.pdf")):
        old_file.unlink()

    # Step 2: Make sure OpenCV can read it (converts AV1 if needed)
    status("Checking video format...")
    readable_path = ensure_readable(video_path)

    # Step 3: Detect and save whiteboard screenshots
    status("Looking for new writing on the whiteboard...")
    screenshot_count = detect_writing(readable_path, video_output, on_progress)

    if screenshot_count == 0:
        raise RuntimeError("No screenshots were extracted.")

    # Step 4: Generate PDF
    status("Creating PDF...")
    pdf_path = create_pdf(video_output)

    return pdf_path


def main():

    print("=" * 55)
    print("          YOUTUBE WHITEBOARD EXTRACTOR")
    print("=" * 55)

    url = input("\nPaste YouTube URL: ").strip()

    if not url:
        print("Error: You did not enter a YouTube URL.")
        return

    try:

        pdf_path = process_video(url)

        print("\n" + "=" * 55)
        print("                 PROCESS COMPLETE")
        print("=" * 55)

        print(f"\nScreenshots: {pdf_path.parent}")
        print(f"PDF: {pdf_path}")

    except KeyboardInterrupt:

        print("\nProcess interrupted by user.")

    except Exception as error:

        print(f"\nERROR: {error}")


# ============================================================
# RUN PROGRAM
# ============================================================

if __name__ == "__main__":
    main()