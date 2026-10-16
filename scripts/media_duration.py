#!/usr/bin/env python3
"""Read YouTube's recording duration without downloading media or using cookies."""

import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def verified(info, video_id):
    if not isinstance(info, dict) or info.get("id") != video_id:
        return {"id": video_id, "error": "invalid_metadata"}
    if info.get("live") or info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        return {"id": video_id, "duration": 0, "live": True}
    duration = info.get("duration")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        return {"id": video_id, "error": "missing_duration"}
    return {"id": video_id, "duration": duration, "live": False}


def extract(video_id):
    executable = shutil.which("yt-dlp")
    if not executable:
        return {"id": video_id, "error": "yt_dlp_missing"}
    command = [executable, "--ignore-config", "--skip-download", "--no-playlist",
               "--ignore-no-formats-error", "--no-warnings", "--quiet",
               "--socket-timeout", "8", "--retries", "1", "--extractor-retries", "1",
               "--dump-single-json", "--", f"https://www.youtube.com/watch?v={video_id}"]

    def _set_pdeathsig():
        try:
            import ctypes
            ctypes.CDLL(None).prctl(1, signal.SIGTERM)
        except Exception:
            pass

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True, preexec_fn=_set_pdeathsig)
    previous_handler = signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        output, _ = process.communicate(timeout=30)
        if process.returncode:
            return {"id": video_id, "error": "lookup_failed"}
        return verified(json.loads(output), video_id)
    except (subprocess.TimeoutExpired, ValueError):
        return {"id": video_id, "error": "lookup_failed"}
    finally:
        # Cancel the extractor and its JavaScript subprocesses with the QML request.
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        signal.signal(signal.SIGTERM, previous_handler)


def duration(video_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return {"error": "invalid_video_id"}
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    cache = state / "nonchalant/media-duration" / f"{video_id}.json"
    try:
        stored = json.loads(cache.read_text())
        if 0 <= time.time() - stored["fetched_at"] < 86400:
            result = verified(stored, video_id)
            if result.get("duration", 0) > 0:
                return result
    except (OSError, ValueError, KeyError, TypeError):
        pass
    result = extract(video_id)
    if result.get("duration", 0) > 0:
        temporary = None
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", dir=cache.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps({**result, "fetched_at": time.time()}))
            temporary.replace(cache)
        except OSError:
            pass
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(duration(sys.argv[1] if len(sys.argv) == 2 else "")))
    except OSError:
        print(json.dumps({"error": "lookup_failed"}))
