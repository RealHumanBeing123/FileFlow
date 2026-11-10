"""Conversion engine: builds and runs FFmpeg commands. No GUI code here."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

# ---------------------------------------------------------------- formats

AUDIO_INPUT = {".flac", ".mp3", ".wav", ".aac", ".m4a", ".ogg", ".oga",
               ".opus", ".wma", ".aiff", ".aif", ".alac", ".ape"}
VIDEO_INPUT = {".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".wmv",
               ".m4v", ".mpg", ".mpeg", ".ts", ".3gp"}
IMAGE_INPUT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
               ".gif", ".heic"}

CATEGORIES = {"Audio": AUDIO_INPUT, "Video": VIDEO_INPUT, "Image": IMAGE_INPUT}

# Output formats offered per category.
OUTPUT_FORMATS = {
    "Audio": ["mp3", "flac", "wav", "m4a", "ogg", "opus", "aac"],
    "Video": ["mp4", "mkv", "webm", "mov", "avi"],
    "Image": ["jpg", "png", "webp", "bmp", "tiff", "gif"],
}

# Quality presets per category. Order matters (shown in the GUI).
QUALITY_LEVELS = {
    "Audio": ["Low (128 kbps)", "Medium (192 kbps)", "High (256 kbps)",
              "Very High (320 kbps)"],
    "Video": ["Low (small file)", "Medium", "High", "Very High (near lossless)"],
    "Image": ["Low", "Medium", "High", "Maximum"],
}
DEFAULT_QUALITY = {"Audio": 2, "Video": 1, "Image": 2}  # index into lists

AUDIO_KBPS = [128, 192, 256, 320]
VIDEO_CRF_H264 = [28, 23, 18, 14]
VIDEO_CRF_VP9 = [40, 33, 28, 22]
JPEG_QSCALE = [15, 8, 3, 1]          # ffmpeg mjpeg: lower = better
WEBP_QUALITY = [50, 75, 90, 100]
PNG_COMPRESSION = [3, 6, 9, 9]       # lossless, only affects size

LOSSLESS_AUDIO = {"flac", "wav"}
# Containers that can carry embedded cover art as a video stream.
COVER_ART_OK = {"mp3", "flac", "m4a"}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def category_of(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return None


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def find_exiftool() -> Optional[str]:
    return shutil.which("exiftool")


def collect_files(source: Path, category: str, recursive: bool = False) -> list[Path]:
    """Return media files of the given category from a file or a folder."""
    exts = CATEGORIES[category]
    if source.is_file():
        return [source] if source.suffix.lower() in exts else []
    it: Iterable[Path] = source.rglob("*") if recursive else source.glob("*")
    return sorted(p for p in it if p.is_file() and p.suffix.lower() in exts)


# ------------------------------------------------------------- commands

def build_command(ffmpeg: str, src: Path, dst: Path, category: str,
                  quality_index: int) -> list[str]:
    fmt = dst.suffix.lower().lstrip(".")
    q = quality_index
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
           "-map_metadata", "0"]

    if category == "Audio":
        if fmt in COVER_ART_OK:
            # Keep embedded cover art when present.
            cmd += ["-map", "0:a:0", "-map", "0:v?", "-c:v", "copy",
                    "-disposition:v", "attached_pic"]
        else:
            cmd += ["-vn"]
        codec = {"mp3": "libmp3lame", "flac": "flac", "wav": "pcm_s16le",
                 "m4a": "aac", "aac": "aac", "ogg": "libvorbis",
                 "opus": "libopus"}[fmt]
        cmd += ["-c:a", codec]
        if fmt not in LOSSLESS_AUDIO:
            cmd += ["-b:a", f"{AUDIO_KBPS[q]}k"]
        if fmt == "mp3":
            cmd += ["-id3v2_version", "3"]

    elif category == "Video":
        # All video, audio and subtitle streams (where the container allows).
        cmd += ["-map", "0:v?", "-map", "0:a?", "-map_chapters", "0"]
        if fmt in ("mp4", "mkv", "mov"):
            cmd += ["-map", "0:s?", "-c:v", "libx264", "-preset", "medium",
                    "-crf", str(VIDEO_CRF_H264[q]), "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-c:s", "srt" if fmt == "mkv" else "mov_text"]
            if fmt in ("mp4", "mov"):
                cmd += ["-movflags", "+faststart"]
        elif fmt == "webm":
            cmd += ["-c:v", "libvpx-vp9", "-b:v", "0",
                    "-crf", str(VIDEO_CRF_VP9[q]), "-row-mt", "1",
                    "-c:a", "libopus", "-b:a", "160k"]
        elif fmt == "avi":
            # mpeg4 qscale: 2 (best) .. 31 (worst)
            cmd += ["-c:v", "mpeg4", "-q:v", str([8, 5, 3, 2][q]),
                    "-c:a", "libmp3lame", "-b:a", "192k"]

    elif category == "Image":
        cmd += ["-frames:v", "1"] if fmt != "gif" else []
        if fmt == "jpg":
            cmd += ["-q:v", str(JPEG_QSCALE[q]), "-pix_fmt", "yuvj420p"]
        elif fmt == "webp":
            cmd += ["-quality", str(WEBP_QUALITY[q])]
        elif fmt == "png":
            cmd += ["-compression_level", str(PNG_COMPRESSION[q])]

    cmd.append(str(dst))
    return cmd


def _copy_image_metadata(exiftool: str, src: Path, dst: Path) -> None:
    """EXIF/IPTC/XMP copy; FFmpeg alone drops most photo metadata."""
    subprocess.run(
        [exiftool, "-TagsFromFile", str(src), "-all:all", "-overwrite_original",
         "-q", "-q", str(dst)],
        capture_output=True, creationflags=_NO_WINDOW)


# ---------------------------------------------------------------- runner

@dataclass
class Result:
    src: Path
    dst: Optional[Path]
    ok: bool
    message: str = ""
    skipped: bool = False


def convert_one(src: Path, out_dir: Path, category: str, fmt: str,
                quality_index: int, ffmpeg: str,
                exiftool: Optional[str] = None) -> Result:
    dst = out_dir / f"{src.stem}.{fmt}"
    if dst.exists():
        # Never overwrite or rename: leave the existing file alone.
        return Result(src, dst, True, "already exists", skipped=True)
    cmd = build_command(ffmpeg, src, dst, category, quality_index)
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        if dst.exists():
            dst.unlink(missing_ok=True)
        return Result(src, None, False, proc.stderr.strip().splitlines()[-1]
                      if proc.stderr.strip() else "FFmpeg failed")
    if category == "Image" and exiftool:
        _copy_image_metadata(exiftool, src, dst)
    return Result(src, dst, True)


def convert_batch(files: list[Path], out_dir: Path, category: str, fmt: str,
                  quality_index: int,
                  on_progress: Callable[[int, int, Result], None],
                  should_cancel: Callable[[], bool] = lambda: False) -> list[Result]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found on PATH. Install it from "
                           "https://ffmpeg.org and restart the app.")
    exiftool = find_exiftool()
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    for i, f in enumerate(files, 1):
        if should_cancel():
            break
        r = convert_one(f, out_dir, category, fmt, quality_index, ffmpeg, exiftool)
        results.append(r)
        on_progress(i, len(files), r)
    return results
