"""FFmpeg service for video probing, normalization, keyframe extraction, and scene change detection."""

import json
import os
import re
import subprocess
from typing import Any


class FFmpegService:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def probe_video(self, video_path: str) -> dict[str, Any]:
        """Probe video file using ffprobe and return metadata dictionary."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cmd = [
            self.ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
        except Exception as e:
            raise RuntimeError(f"FFprobe execution failed on {video_path}: {e}")

        # Extract video stream
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        duration = float(data.get("format", {}).get("duration", 0.0))
        if not duration and video_stream:
            duration = float(video_stream.get("duration", 0.0))

        width = int(video_stream.get("width", 0)) if video_stream else 0
        height = int(video_stream.get("height", 0)) if video_stream else 0

        # Calculate FPS
        fps = 30.0
        if video_stream and "r_frame_rate" in video_stream:
            try:
                num, den = video_stream["r_frame_rate"].split("/")
                fps = round(float(num) / float(den), 2)
            except Exception:
                fps = 30.0

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "codec": video_stream.get("codec_name", "unknown") if video_stream else "unknown",
            "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
            "is_vertical": height > width if width > 0 else True,
        }

    def extract_frame_at_timestamp(self, video_path: str, timestamp_sec: float, output_path: str) -> str:
        """Extract a single high-quality frame at timestamp using FFmpeg."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-ss", str(max(0.0, timestamp_sec)),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"Failed to extract frame at {timestamp_sec}s: {res.stderr}")
        return output_path

    def extract_keyframes(self, video_path: str, timestamps: list[float], output_dir: str) -> list[str]:
        """Extract multiple frames for given timestamps."""
        os.makedirs(output_dir, exist_ok=True)
        extracted = []
        for idx, ts in enumerate(timestamps):
            out_file = os.path.join(output_dir, f"frame_{idx + 1}_{int(ts * 100)}.jpg")
            try:
                self.extract_frame_at_timestamp(video_path, ts, out_file)
                extracted.append(out_file)
            except Exception:
                pass
        return extracted

    def detect_scene_timestamps(self, video_path: str, max_points: int = 3) -> list[float]:
        """Detect scene change timestamps or return evenly distributed points."""
        meta = self.probe_video(video_path)
        duration = meta.get("duration", 10.0)

        # Fallback points if video is very short
        if duration <= 3.0:
            return [0.5, 1.0, 1.5]

        # Use FFmpeg scene detection
        cmd = [
            self.ffmpeg_bin,
            "-i", video_path,
            "-vf", "select='gt(scene,0.25)',showinfo",
            "-f", "null",
            "-",
        ]
        timestamps = []
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            matches = re.findall(r"pts_time:([0-9\.]+)", res.stderr)
            for m in matches:
                ts = float(m)
                if 0.5 <= ts <= (duration - 0.5):
                    timestamps.append(round(ts, 2))
                if len(timestamps) >= max_points:
                    break
        except Exception:
            pass

        # If not enough scene changes detected, pick evenly spaced points (15%, 45%, 75% of duration)
        if len(timestamps) < max_points:
            proportions = [0.15, 0.45, 0.75]
            for p in proportions:
                ts = round(duration * p, 2)
                if ts not in timestamps and ts > 0:
                    timestamps.append(ts)
                if len(timestamps) >= max_points:
                    break

        return sorted(timestamps[:max_points])

    def normalize_video_9_16(self, input_path: str, output_path: str) -> str:
        """Normalize video to MP4 H264/AAC with 1080x1920 (9:16) resolution."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Filter: Scale to fit inside 1080x1920 while preserving aspect ratio, pad with black bars if needed
        vf_filter = (
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
            "format=yuv420p"
        )

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", input_path,
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-movflags", "+faststart",
            output_path,
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"Video normalization failed: {res.stderr}")
        return output_path


ffmpeg_service = FFmpegService()
