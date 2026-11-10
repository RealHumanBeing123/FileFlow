# Media Converter

A simple desktop app (Python + Tkinter) that converts media files between formats using FFmpeg.

- Convert a single file, or every matching file in a folder (optionally including subfolders)
- Output folder is required; originals are never touched. If a file with the same name already exists in the output folder, it is skipped (not overwritten, not renamed) and the log shows `SKIP`
- Quality levels for audio (bitrate), video (CRF), and images (JPEG/WebP quality)
- Metadata is carried over (tags, cover art, chapters, EXIF)

I know a little bit about video files, a fair bit about audio, but nothing about images. 
Hopefully the image stuff isn't useless but if it is then ¯\\\_(ツ)\_/¯

Screenshot

<img width="511" height="375" alt="FileFlow" src="https://github.com/user-attachments/assets/76d28a55-b684-486d-be4c-f0eddbe101f9" />


## Requirements

- Python 3.10+ (Tkinter is included with the standard installers; on Debian/Ubuntu: `sudo apt install python3-tk`)
- [FFmpeg](https://ffmpeg.org) on your PATH (required)
- [ExifTool](https://exiftool.org) on your PATH (optional, but recommended: copies full EXIF/IPTC/XMP photo metadata)

No pip packages needed.

Set up (if not using the .exe):
1. Download and unzip the files to where your heart desires
2. CD to that folder
3. To compile
   ```pyinstaller --onefile --windowed --name MediaConverter app.py```
4. To run it
  ```python app.py```

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

## While the software doesn't support extracting audio, I'm going to provide you with the simple command for that. 

One file at a time:

```ffmpeg -i "example.mp4" "example.mp3"```

For batch extraction/conversion:

```FOR /F "tokens=*" %G IN ('dir /b *.flac') DO ffmpeg -i "%G" -acodec mp3 "%~nG.mp3"```

For shortening a video or audio file without putting it into something like [ReelForge for video editing.](https://github.com/RealHumanBeing123/ReelForge)

```ffmpeg <start time> <input file> <cut duration> <out file>```

```ffmpeg -ss 01:23:45 -i "FullThing.mp4" -to 00:06:00 -c copy "ShortenedThing.mp4"```
