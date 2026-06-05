"""
Video Super-Resolution Upscaler
Supports two modes:
  --mode simple  : FFmpeg Lanczos interpolation (fast, no GPU needed)
  --mode ai      : Real-ESRGAN AI upscaling (best quality, GPU optional)
"""

import argparse
import os
import re
import sys
import time
import subprocess
import shutil
import tempfile
from pathlib import Path

_TIME_RE  = re.compile(r"time=(\d+):(\d+):([\d.]+)")
_FPS_RE   = re.compile(r"fps=\s*([\d.]+)")
_SPEED_RE = re.compile(r"speed=\s*([\d.]+)x")


def find_ffmpeg():
    """Locate ffmpeg.exe, reading registry PATH so stale-environment callers still work."""
    # 1. Current process PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 2. Read the real current PATH from Windows registry (catches winget installs
    #    that updated PATH after this process was launched).
    search_dirs: list[str] = []
    if sys.platform == "win32":
        try:
            import winreg
            for hive, sub in [
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                (winreg.HKEY_CURRENT_USER,  r"Environment"),
            ]:
                with winreg.OpenKey(hive, sub) as key:
                    val, _ = winreg.QueryValueEx(key, "PATH")
                    search_dirs.extend(val.split(";"))
        except Exception:
            pass

    for d in search_dirs:
        p = Path(d.strip()) / "ffmpeg.exe"
        if p.exists():
            return str(p)

    # 3. Glob winget packages directory
    local_app = Path(os.environ.get("LOCALAPPDATA", ""))
    for pattern in [
        local_app / "Microsoft/WinGet/Links/ffmpeg.exe",
        local_app / "Microsoft/WinGet/Packages/Gyan.FFmpeg*/**/bin/ffmpeg.exe",
    ]:
        hits = list(Path(local_app).parent.parent.glob(str(pattern))) if "**" in str(pattern) \
               else ([pattern] if pattern.exists() else [])
        # use glob properly
        if "**" in str(pattern):
            hits = list(local_app.glob(str(pattern.relative_to(local_app))))
        if hits:
            return str(hits[0])

    # 4. Other common manual install locations
    for p in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if Path(p).exists():
            return p

    return None


def _parse_time(h, m, s) -> float:
    return int(h) * 3600 + int(m) * 60 + float(s)


def _run_ffmpeg(cmd: list, duration: float, output_path: str):
    """Run FFmpeg, printing PROGRESS: lines so the GUI can track progress."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
        creationflags=flags,
    )
    t0 = time.time()
    try:
        for raw in proc.stderr:
            m = _TIME_RE.search(raw)
            if not m:
                continue
            cur = _parse_time(*m.groups())
            pct = min(cur / duration * 100, 99.9) if duration > 0 else 0
            fps_m   = _FPS_RE.search(raw)
            speed_m = _SPEED_RE.search(raw)
            fps   = fps_m.group(1)   if fps_m   else "?"
            speed = speed_m.group(1) if speed_m else "?"
            elapsed = time.time() - t0
            eta = max(elapsed / (pct / 100) - elapsed, 0) if pct > 0 else 0
            # Structured line for GUI — prefix keeps it out of user-visible log
            print(f"PROGRESS:{pct:.1f}:{fps}:{speed}:{eta:.0f}", flush=True)
    finally:
        proc.wait()

    if proc.returncode != 0:
        _cleanup(output_path)
        raise subprocess.CalledProcessError(proc.returncode, cmd)


def _cleanup(path: str):
    """Delete an incomplete output file, ignoring errors if it's already gone or locked."""
    try:
        p = Path(path)
        if p.exists():
            p.unlink()
            print(f"  (removed incomplete file: {p.name})")
    except OSError:
        pass


def get_video_info(ffprobe, input_path):
    """Return (width, height, fps, duration) for the input video."""
    import json
    cmd = [
        ffprobe, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)

    width = height = fps = duration = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream["width"]
            height = stream["height"]
            r = stream.get("r_frame_rate", "30/1").split("/")
            fps = round(int(r[0]) / int(r[1]), 3) if len(r) == 2 else 30
            duration = float(data.get("format", {}).get("duration", 0))
            break
    return width, height, fps, duration


def upscale_simple(input_path, output_path, target_w, target_h, ffmpeg, ffprobe):
    """FFmpeg Lanczos upscaling — fast, no AI."""
    w, h, fps, dur = get_video_info(ffprobe, input_path)
    print(f"  Source  : {w}x{h}  {fps} fps  {dur:.1f}s")
    print(f"  Target  : {target_w}x{target_h}")
    print(f"  Method  : Lanczos interpolation (FFmpeg)")

    cmd = [
        ffmpeg, "-i", input_path,
        "-vf", f"scale={target_w}:{target_h}:flags=lanczos",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-y", output_path
    ]
    print("\nRunning FFmpeg ...\n")
    try:
        _run_ffmpeg(cmd, dur, output_path)
    except KeyboardInterrupt:
        _cleanup(output_path)
        raise
    print(f"\nDone: {output_path}")


def upscale_ai(input_path, output_path, scale, ffmpeg, ffprobe, model_name):
    """
    Real-ESRGAN AI upscaling pipeline (chunked to support long videos):
      For each 60-second chunk:
        1. Extract frames (FFmpeg)
        2. Super-resolve each frame (Real-ESRGAN)
        3. Encode chunk to a temp segment (FFmpeg)
      Finally: concatenate all segments + original audio.
    """
    try:
        import cv2
        import numpy as np
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
    except ImportError:
        print("\n[ERROR] AI dependencies not installed.")
        print("Run: pip install realesrgan basicsr opencv-python torch torchvision")
        print("\nFalling back to simple Lanczos mode ...\n")
        ffprobe = str(Path(ffmpeg).parent / "ffprobe.exe")
        w, h, *_ = get_video_info(ffprobe, input_path)
        upscale_simple(input_path, output_path, w * scale, h * scale, ffmpeg, ffprobe)
        return

    w, h, fps, dur = get_video_info(ffprobe, input_path)
    print(f"  Source  : {w}x{h}  {fps} fps  {dur:.1f}s")
    print(f"  Target  : {w*scale}x{h*scale}  (x{scale})")
    print(f"  Model   : {model_name}")

    # ── Model selection ─────────────────────────────────────────────────────
    model_map = {
        "RealESRGAN_x4plus": (RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4), 4),
        "RealESRGAN_x2plus": (RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2), 2),
    }
    if model_name not in model_map:
        print(f"[WARN] Unknown model '{model_name}', defaulting to RealESRGAN_x4plus")
        model_name = "RealESRGAN_x4plus"
    model, model_scale = model_map[model_name]

    try:
        import torch
        use_gpu = torch.cuda.is_available()
    except ImportError:
        use_gpu = False

    if use_gpu:
        import torch
        print(f"  GPU     : {torch.cuda.get_device_name(0)} (CUDA — FP16 啟用)")
    else:
        print("  [警告] 未偵測到 CUDA GPU，使用 CPU 處理。")
        print("         1 小時影片在 CPU 上可能需要數天，強烈建議安裝 CUDA 版 PyTorch。")

    upsampler = RealESRGANer(
        scale=model_scale,
        model_path=f"https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/{model_name}.pth",
        model=model,
        tile=512,
        tile_pad=10,
        pre_pad=0,
        half=use_gpu,
    )

    CHUNK_SECS = 60  # seconds per processing chunk — limits peak disk usage

    with tempfile.TemporaryDirectory(prefix="upscale_") as tmp:
        frames_in  = Path(tmp) / "in"
        frames_out = Path(tmp) / "out"
        segs_dir   = Path(tmp) / "segs"
        frames_in.mkdir(); frames_out.mkdir(); segs_dir.mkdir()

        total_frames   = max(1, int(fps * dur))
        processed      = 0
        seg_paths: list[Path] = []
        chunk_idx      = 0
        start_t        = 0.0
        t0_ai          = time.time()

        while start_t < dur:
            chunk_dur = min(CHUNK_SECS, dur - start_t)

            # ── clear frame dirs from previous chunk ────────────────────────
            for f in frames_in.glob("*.png"):
                f.unlink()
            for f in frames_out.glob("*.png"):
                f.unlink()

            print(f"\n[Chunk {chunk_idx + 1}]  {start_t:.1f}s – {start_t + chunk_dur:.1f}s")

            # Step 1: extract this chunk's frames
            subprocess.run([
                ffmpeg, "-ss", str(start_t), "-i", input_path,
                "-t", str(chunk_dur), "-vsync", "0",
                str(frames_in / "%08d.png"), "-y",
            ], check=True, capture_output=True)

            frame_files = sorted(frames_in.glob("*.png"))
            n = len(frame_files)
            if n == 0:
                break

            # Step 2: AI upscale each frame in this chunk
            for i, frame_path in enumerate(frame_files, 1):
                img = cv2.imread(str(frame_path), cv2.IMREAD_UNCHANGED)
                out_img, _ = upsampler.enhance(img, outscale=scale)
                cv2.imwrite(str(frames_out / frame_path.name), out_img)
                processed += 1
                pct     = min(processed / total_frames * 100, 99.9)
                elapsed = time.time() - t0_ai
                fps_ai  = processed / elapsed if elapsed > 0 else 0
                eta     = (total_frames - processed) / fps_ai if fps_ai > 0 else 0
                print(f"PROGRESS:{pct:.1f}:{fps_ai:.2f}:AI:{eta:.0f}", flush=True)
            print()

            # Step 3: encode chunk frames to a segment (no audio)
            seg_path = segs_dir / f"seg_{chunk_idx:04d}.mp4"
            subprocess.run([
                ffmpeg,
                "-framerate", str(fps),
                "-i", str(frames_out / "%08d.png"),
                "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-y", str(seg_path),
            ], check=True, capture_output=True)
            seg_paths.append(seg_path)

            start_t   += chunk_dur
            chunk_idx += 1

        # ── Concatenate all segments and mux original audio ──────────────────
        print("\n[Final] Concatenating segments and adding audio ...")
        concat_list = segs_dir / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.name}'" for p in seg_paths),
            encoding="utf-8",
        )

        concat_cmd = [
            ffmpeg,
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-i", input_path,
            "-map", "0:v", "-map", "1:a?",
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-y", output_path,
        ]
        try:
            _run_ffmpeg(concat_cmd, dur, output_path)
        except KeyboardInterrupt:
            _cleanup(output_path)
            raise

    print(f"\nDone: {output_path}")


def resolve_target(w, h, target_res):
    """
    Given source (w, h) and a target like '1080p', '4k', or '1920x1080',
    return (target_w, target_h, scale_factor).
    """
    presets = {
        "480p":  (854,  480),
        "720p":  (1280, 720),
        "1080p": (1920, 1080),
        "1440p": (2560, 1440),
        "4k":    (3840, 2160),
    }
    if target_res.lower() in presets:
        tw, th = presets[target_res.lower()]
    elif "x" in target_res.lower():
        tw, th = map(int, target_res.lower().split("x"))
    else:
        raise ValueError(f"Unrecognised target resolution: '{target_res}'. "
                         "Use e.g. 1080p, 4k, 1920x1080")

    scale = max(tw / w, th / h)
    return tw, th, scale


def main():
    parser = argparse.ArgumentParser(
        description="Upscale video resolution using Lanczos or AI super-resolution"
    )
    parser.add_argument("input",  help="Input video file (e.g. video.mp4)")
    parser.add_argument("output", nargs="?", help="Output file (default: input_upscaled.mp4)")
    parser.add_argument("--target", default="1080p",
                        help="Target resolution: 720p, 1080p, 4k, or WxH (default: 1080p)")
    parser.add_argument("--mode", choices=["simple", "ai"], default="simple",
                        help="Upscaling mode: simple=FFmpeg Lanczos, ai=Real-ESRGAN (default: simple)")
    parser.add_argument("--model", default="RealESRGAN_x4plus",
                        choices=["RealESRGAN_x4plus", "RealESRGAN_x2plus"],
                        help="AI model to use (only in ai mode)")
    args = parser.parse_args()

    # ── Validate input ───────────────────────────────────────────────────────
    input_path = str(Path(args.input).resolve())
    if not Path(input_path).exists():
        sys.exit(f"[ERROR] Input file not found: {input_path}")

    stem = Path(input_path).stem
    suffix = Path(input_path).suffix or ".mp4"
    output_path = args.output or str(Path(input_path).parent / f"{stem}_upscaled{suffix}")

    # ── Locate FFmpeg ────────────────────────────────────────────────────────
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        sys.exit("[ERROR] ffmpeg not found. Install via: winget install Gyan.FFmpeg")
    ffprobe = str(Path(ffmpeg).parent / "ffprobe.exe")

    w, h, fps, dur = get_video_info(ffprobe, input_path)
    target_w, target_h, scale = resolve_target(w, h, args.target)

    print(f"\n{'='*54}")
    print(f"  Video Upscaler")
    print(f"{'='*54}")
    print(f"  Input   : {Path(input_path).name}")
    print(f"  Output  : {Path(output_path).name}")
    print(f"  Mode    : {args.mode.upper()}")

    if args.mode == "simple":
        upscale_simple(input_path, output_path, target_w, target_h, ffmpeg, ffprobe)
    else:
        # For AI mode, scale must be integer (2 or 4)
        ai_scale = 4 if scale >= 3 else 2
        upscale_ai(input_path, output_path, ai_scale, ffmpeg, ffprobe, args.model)


if __name__ == "__main__":
    main()
