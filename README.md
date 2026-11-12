# Video2Notes

Turn a YouTube lecture into PDF notes. Video2Notes watches the video, saves a
screenshot whenever new writing appears on the whiteboard, removes duplicate
and near-duplicate screenshots, and puts the rest into one PDF.

## Download (Windows)

1. Open the [Releases page](https://github.com/scatterfah/Video2Notes/releases/latest).
2. Download **Video2Notes-Setup.exe** and run it.
3. Open **Video2Notes** from the Start menu or the desktop icon.

Nothing else needs to be installed.

**Windows may warn you.** The app is not digitally signed yet, so Windows can show
"Windows protected your PC". Click **More info**, then **Run anyway**. On some
computers, Smart App Control blocks unsigned apps completely. Signing the app is
planned.

## How to use

1. Paste a YouTube link.
2. Choose a detail level:
   - One page per finished board
   - Balanced (recommended)
   - Detailed (more steps)
3. Press **Start** and wait for the progress bar to finish.
4. Press **Open PDF**.

Your files are saved in `Documents\WhiteboardExtractor\extracted_notes\<video id>\`.
Screenshots removed as duplicates are moved to a `skipped` folder there, so
nothing is lost.

## Limitations

- It looks for changes on the screen, so it works best on handwriting on a plain
  board. A webcam picture of the teacher, a moving hand, or scrolling can cause
  extra pages.
- Very faint or yellow writing on a white board may not be detected.
- Results are not perfect. Check the PDF and the `skipped` folder.

## Run from source

Requirements: Python 3.10 or newer, [FFmpeg](https://ffmpeg.org) and
[Deno](https://deno.com) installed and available in your PATH.

    git clone https://github.com/scatterfah/Video2Notes.git
    cd Video2Notes
    python3 -m venv .venv
    source .venv/bin/activate        (Windows: .venv\Scripts\activate)
    pip install -r requirements.txt
    python app.py

On Linux you may also need the tkinter package (Fedora: `sudo dnf install python3-tkinter`).

## Legal

Use this tool for personal study. Downloading videos may be against the terms of
the video platform, and the videos belong to their creators, so respect their
rights. This project is not affiliated with YouTube or Google.

## License

MIT. See [LICENSE](LICENSE). Bundled third-party software is listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
