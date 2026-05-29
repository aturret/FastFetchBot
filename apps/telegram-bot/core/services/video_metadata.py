import asyncio
import json
import os
import shutil
import tempfile

from fastfetchbot_shared.models.classes import NamedBytesIO
from fastfetchbot_shared.utils.logger import logger
from fastfetchbot_shared.utils.number import positive_int

VIDEO_METADATA_FIELDS = ("width", "height", "duration")
VIDEO_METADATA_PROBE_CONCURRENCY = 2
VIDEO_TEMP_FILE_CHUNK_SIZE = 1024 * 1024
_video_metadata_probe_semaphore = asyncio.Semaphore(VIDEO_METADATA_PROBE_CONCURRENCY)


def video_metadata_from_mapping(media_item: dict) -> dict[str, int]:
    metadata = {}
    for field in VIDEO_METADATA_FIELDS:
        value = positive_int(media_item.get(field))
        if value is not None:
            metadata[field] = value
    return metadata


def video_input_kwargs(media_item: dict) -> dict:
    return {
        "supports_streaming": True,
        **video_metadata_from_mapping(media_item),
    }


def _video_rotation(stream: dict) -> int:
    tags = stream.get("tags") or {}
    rotation = tags.get("rotate")
    if rotation is None:
        for side_data in stream.get("side_data_list") or []:
            if "rotation" in side_data:
                rotation = side_data["rotation"]
                break
    try:
        value = positive_int(abs(float(rotation))) if rotation is not None else None
    except (TypeError, ValueError):
        value = None
    return value or 0


def _write_video_temp_file(
    io_object: NamedBytesIO,
    temp_file,
    original_position: int,
) -> None:
    try:
        io_object.seek(0)
        while chunk := io_object.read(VIDEO_TEMP_FILE_CHUNK_SIZE):
            temp_file.write(chunk)
        temp_file.flush()
    finally:
        io_object.seek(original_position)


async def probe_video_metadata(io_object: NamedBytesIO) -> dict[str, int]:
    """Read video dimensions from the file so Telegram iOS receives explicit aspect data."""
    # TODO: This bot-side ffprobe path is a workaround for Telegram iOS aspect ratio bugs.
    # Move media download/probing into the worker-backed MediaAsset cache instead.
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        logger.debug(
            "ffprobe is not available; sending video without probed dimensions"
        )
        return {}

    file_name = str(getattr(io_object, "name", "") or "")
    suffix = os.path.splitext(file_name)[1] or ".mp4"
    original_position = io_object.tell()

    async with _video_metadata_probe_semaphore:
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
                await asyncio.to_thread(
                    _write_video_temp_file,
                    io_object,
                    temp_file,
                    original_position,
                )

                process = await asyncio.create_subprocess_exec(
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,duration:stream_tags=rotate:stream_side_data=rotation",
                    "-of",
                    "json",
                    temp_file.name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(
                    f"ffprobe failed for {file_name or 'video'}: {stderr.decode(errors='ignore')}"
                )
                return {}

            data = json.loads(stdout.decode() or "{}")
            streams = data.get("streams") or []
            if not streams:
                return {}

            stream = streams[0]
            width = positive_int(stream.get("width"))
            height = positive_int(stream.get("height"))
            if width and height and _video_rotation(stream) % 180 == 90:
                width, height = height, width

            metadata = {}
            if width is not None:
                metadata["width"] = width
            if height is not None:
                metadata["height"] = height
            duration = positive_int(stream.get("duration"))
            if duration is not None:
                metadata["duration"] = duration
            return metadata
        except Exception:
            logger.exception(
                f"Failed to probe video metadata for {file_name or 'video'}"
            )
            return {}
        finally:
            try:
                io_object.seek(original_position)
            except Exception:
                logger.exception(
                    "Failed to restore video stream position after probing"
                )


async def ensure_video_metadata(media_item: dict, io_object: NamedBytesIO) -> None:
    if media_item["media_type"] != "video":
        return
    metadata = video_metadata_from_mapping(media_item)
    if "width" in metadata and "height" in metadata:
        return
    probed_metadata = await probe_video_metadata(io_object)
    for field, value in probed_metadata.items():
        if positive_int(media_item.get(field)) is None:
            media_item[field] = value
