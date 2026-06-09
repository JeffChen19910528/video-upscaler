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
import threading
import subprocess
import shutil
import tempfile
from pathlib import Path
from queue import Queue

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


def _check_nvenc(ffmpeg: str) -> bool:
    """Return True if h264_nvenc hardware encoder is available."""
    try:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        return "h264_nvenc" in r.stdout
    except Exception:
        return False


def _encoder_args(use_nvenc: bool) -> list[str]:
    if use_nvenc:
        # NVENC: hardware H.264 encoding on NVIDIA GPU
        return ["-c:v", "h264_nvenc", "-rc", "vbr", "-cq", "18",
                "-preset", "p4", "-b:v", "0"]
    return ["-c:v", "libx264", "-crf", "18", "-preset", "medium"]


def _auto_tile_size(use_gpu: bool) -> int:
    """Pick Real-ESRGAN tile size based on available GPU VRAM."""
    if not use_gpu:
        return 256
    try:
        import torch
        vram = torch.cuda.get_device_properties(0).total_memory
        # Use 7.5 GiB threshold: NVIDIA "8GB" cards report ~7.8 GiB actual
        if vram >= 7.5 * 1024 ** 3:
            return 0    # no tiling — fastest (≥8 GB VRAM)
        if vram >= 5.5 * 1024 ** 3:
            return 768
        if vram >= 3.5 * 1024 ** 3:
            return 512
        return 256
    except Exception:
        return 512


def _upscale_frames_threaded(upsampler, frame_files, frames_out, scale,
                              total_frames, processed_offset, t0_ai) -> int:
    """
    Threaded read → GPU → write pipeline so the GPU never idles on disk I/O.

    Reader thread pre-loads PNG frames into a queue while the main thread
    feeds them to the GPU. Writer thread flushes results asynchronously.
    Returns the updated processed-frame count.
    """
    READ_BUF  = 8
    WRITE_BUF = 8

    read_q  = Queue(maxsize=READ_BUF)
    write_q = Queue(maxsize=WRITE_BUF)

    def _reader():
        import cv2
        for fp in frame_files:
            img = cv2.imread(str(fp), cv2.IMREAD_UNCHANGED)
            read_q.put((fp.name, img))
        read_q.put(None)  # sentinel

    def _writer():
        import cv2
        while True:
            item = write_q.get()
            if item is None:
                break
            name, img = item
            cv2.imwrite(str(frames_out / name), img)

    rt = threading.Thread(target=_reader, daemon=True)
    wt = threading.Thread(target=_writer, daemon=True)
    rt.start()
    wt.start()

    processed = processed_offset
    while True:
        item = read_q.get()
        if item is None:
            break
        name, img = item
        out_img, _ = upsampler.enhance(img, outscale=scale)
        write_q.put((name, out_img))
        processed += 1
        pct     = min(processed / total_frames * 100, 99.9)
        elapsed = time.time() - t0_ai
        fps_ai  = processed / elapsed if elapsed > 0 else 0
        eta     = (total_frames - processed) / fps_ai if fps_ai > 0 else 0
        print(f"PROGRESS:{pct:.1f}:{fps_ai:.2f}:AI:{eta:.0f}", flush=True)

    write_q.put(None)
    rt.join()
    wt.join()
    return processed


def get_video_info(ffprobe, input_path):
    """Return (width, height, fps, duration) for the input video."""
    import json
    cmd = [
        ffprobe, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", input_path
    ]
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace')
    if not result.stdout or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed on '{input_path}': {result.stderr.strip()}")
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
    # Auto-select x2plus for x2 upscaling: x4plus internally produces a 4x
    # intermediate (5120×2880 for 720p input) then downscales — pure waste.
    if scale == 2 and model_name == "RealESRGAN_x4plus":
        model_name = "RealESRGAN_x2plus"
        print("  [Auto]  Switched to RealESRGAN_x2plus for x2 upscaling (3–5× faster)")

    model_urls = {
        "RealESRGAN_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "RealESRGAN_x2plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    }
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
        torch.backends.cudnn.benchmark = True
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
        print(f"  GPU     : {torch.cuda.get_device_name(0)} (CUDA — FP16 啟用, {vram_gb:.1f} GB VRAM)")
    else:
        import torch as _t
        ver = _t.__version__
        is_cpu_build = "+cpu" in ver
        print(f"  [錯誤] GPU 無法使用！PyTorch 版本：{ver}")
        if is_cpu_build:
            print("  ► 原因：安裝的是 CPU 版 PyTorch，沒有 CUDA 支援。")
            print("  ► 修復：在程式介面按「安裝 AI 套件」重新安裝，")
            print("         或執行：pip install torch torchvision")
            print("                  --index-url https://download.pytorch.org/whl/cu128")
        else:
            print("  ► 原因：CUDA 驅動程式或版本不符，請確認 NVIDIA 驅動已正確安裝。")
        print("  ► 目前退回 CPU 處理，速度將非常慢。")

    tile_size = _auto_tile_size(use_gpu)
    tile_label = "無分塊" if tile_size == 0 else str(tile_size)
    print(f"  Tile    : {tile_label}  (依 VRAM 自動選擇)")

    use_nvenc = use_gpu and _check_nvenc(ffmpeg)
    enc_label = "h264_nvenc (GPU)" if use_nvenc else "libx264 (CPU)"
    print(f"  Encoder : {enc_label}")

    upsampler = RealESRGANer(
        scale=model_scale,
        model_path=model_urls[model_name],
        model=model,
        tile=tile_size,
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

            # Step 2: AI upscale — threaded I/O keeps GPU busy
            processed = _upscale_frames_threaded(
                upsampler, frame_files, frames_out, scale,
                total_frames, processed, t0_ai,
            )
            print()

            # Step 3: encode chunk frames to a segment (NVENC when available)
            seg_path = segs_dir / f"seg_{chunk_idx:04d}.mp4"
            subprocess.run([
                ffmpeg,
                "-framerate", str(fps),
                "-i", str(frames_out / "%08d.png"),
                *_encoder_args(use_nvenc),
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
