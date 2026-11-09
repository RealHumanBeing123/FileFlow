# Media Converter

A simple desktop app (Python + Tkinter) that converts media files between formats using FFmpeg.

- Convert a single file, or every matching file in a folder (optionally including subfolders)
- Output folder is required; originals are never touched and existing files are never overwritten (`song (1).mp3`)
- Quality levels for audio (bitrate), video (CRF), and images (JPEG/WebP quality)
- Metadata is carried over (tags, cover art, chapters, EXIF)

## Requirements

- Python 3.10+ (Tkinter is included with the standard installers; on Debian/Ubuntu: `sudo apt install python3-tk`)
- [FFmpeg](https://ffmpeg.org) on your PATH (required)
- [ExifTool](https://exiftool.org) on your PATH (optional, but recommended: copies full EXIF/IPTC/XMP photo metadata)

No pip packages needed.

## Run

```
python app.py
```

## Supported formats

| Type  | Inputs | Outputs |
|-------|--------|---------|
| Audio | flac, mp3, wav, aac, m4a, ogg, opus, wma, aiff, alac, ape | mp3, flac, wav, m4a, ogg, opus, aac |
| Video | mkv, mp4, avi, mov, webm, flv, wmv, m4v, mpg, ts, 3gp | mp4, mkv, webm, mov, avi |
| Image | jpg, png, webp, bmp, tiff, gif, heic* | jpg, png, webp, bmp, tiff, gif |

*HEIC input depends on your FFmpeg build.

## Quality levels

- **Audio:** 128 / 192 / 256 / 320 kbps (ignored for lossless FLAC and WAV)
- **Video:** CRF-based (H.264 for mp4/mkv/mov, VP9 for webm, MPEG-4 for avi): Low, Medium, High, Very High
- **Images:** JPEG and WebP quality; PNG compression effort (lossless)

## Metadata notes

Text tags (artist, title, dates, etc.), chapters and cover art are kept where the target format supports them. Formats differ in what they can store, so a few fields may not map across (e.g. some ID3 frames to Vorbis comments). Photo EXIF is copied with ExifTool when installed; without it only what FFmpeg can carry over is kept.

## Layout

- `converter.py`: conversion engine (no GUI; usable from scripts)
- `app.py`: Tkinter interface
