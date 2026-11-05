"""Validate bounded uploads before publishing their media URLs."""

import json
import subprocess
from pathlib import Path

from PIL import Image


class InvalidMedia(ValueError):
    pass


class ProbeUnavailable(RuntimeError):
    pass


def validate(path: Path, extension: str) -> None:
    if extension == ".mp4":
        _validate_video(path)
        return

    expected_format = "PNG" if extension == ".png" else "JPEG"
    try:
        with Image.open(path, formats=[expected_format]) as image:
            image.verify()
        # JPEG verify alone does not detect truncated scan data.
        with Image.open(path, formats=[expected_format]) as image:
            image.load()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidMedia from exc


def _validate_video(path: Path) -> None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file",
                "-f",
                "mov",
                "-enable_drefs",
                "0",
                "-count_packets",
                "-show_entries",
                "stream=codec_type,codec_name,nb_read_packets",
                "-of",
                "json",
                "-i",
                str(path.resolve()),
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        raise ProbeUnavailable from exc
    except subprocess.TimeoutExpired as exc:
        raise InvalidMedia from exc

    if result.returncode or result.stderr:
        raise InvalidMedia
    streams = json.loads(result.stdout).get("streams", [])
    has_video = any(
        stream["codec_type"] == "video"
        and stream.get("codec_name") == "h264"
        and stream.get("nb_read_packets", "0").isdigit()
        and int(stream.get("nb_read_packets", "0")) > 0
        for stream in streams
    )
    if not has_video or any(
        stream["codec_type"] == "audio" and stream.get("codec_name") != "aac"
        for stream in streams
    ):
        raise InvalidMedia
