"""
Batch Video Upscaler (CLI)
Process all videos in a folder with the same settings.

Usage:
  python batch_upscale.py <input_folder> [output_folder] [options]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv",
              ".webm", ".m4v", ".ts", ".mts", ".mpg", ".mpeg"}

UPSCALE_PY = Path(__file__).parent / "upscale.py"


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def process_file(src: Path, dst: Path, args) -> bool:
    cmd = [sys.executable, str(UPSCALE_PY), str(src), str(dst),
           "--target", args.target, "--mode", args.mode]
    if args.mode == "ai":
        cmd += ["--model", args.model]

    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Batch upscale all videos in a folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_upscale.py ./raw_videos --target 1080p
  python batch_upscale.py ./raw_videos ./output --mode ai --target 4k
  python batch_upscale.py ./raw_videos --recursive --target 720p
        """
    )
    parser.add_argument("input_dir",        help="Folder containing source videos")
    parser.add_argument("output_dir",       nargs="?", help="Output folder (default: input_dir/upscaled)")
    parser.add_argument("--target",         default="1080p",
                        choices=["480p", "720p", "1080p", "1440p", "4k"],
                        help="Target resolution (default: 1080p)")
    parser.add_argument("--mode",           default="simple", choices=["simple", "ai"],
                        help="Upscale method: simple=Lanczos, ai=Real-ESRGAN (default: simple)")
    parser.add_argument("--model",          default="RealESRGAN_x4plus",
                        choices=["RealESRGAN_x4plus", "RealESRGAN_x2plus"],
                        help="AI model (ai mode only)")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="Search subfolders recursively")
    parser.add_argument("--skip-existing",  action="store_true",
                        help="Skip files that already exist in output folder")
    args = parser.parse_args()

    # ── Validate ──────────────────────────────────────────────────────────
    if not UPSCALE_PY.exists():
        sys.exit(f"[ERROR] upscale.py not found at {UPSCALE_PY}")

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        sys.exit(f"[ERROR] Not a directory: {input_dir}")

    output_dir = Path(args.output_dir) if args.output_dir else input_dir / "upscaled"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Collect files ─────────────────────────────────────────────────────
    pattern = "**/*" if args.recursive else "*"
    files = sorted(f for f in input_dir.glob(pattern) if f.suffix.lower() in VIDEO_EXTS)

    if not files:
        print(f"No video files found in: {input_dir}")
        return

    print(f"\n{'='*60}")
    print(f"  Batch Video Upscaler")
    print(f"{'='*60}")
    print(f"  Input     : {input_dir}")
    print(f"  Output    : {output_dir}")
    print(f"  Target    : {args.target}")
    print(f"  Mode      : {args.mode.upper()}")
    print(f"  Files     : {len(files)}")
    print(f"{'='*60}\n")

    # ── Process ───────────────────────────────────────────────────────────
    ok_list   = []
    fail_list = []
    skip_list = []
    batch_start = time.time()

    for i, src in enumerate(files, 1):
        out = output_dir / (src.stem + "_upscaled" + src.suffix)

        prefix = f"[{i:>{len(str(len(files)))}} / {len(files)}]"

        if args.skip_existing and out.exists():
            print(f"{prefix}  SKIP  {src.name}")
            skip_list.append(src.name)
            continue

        print(f"{prefix}  ►  {src.name}")
        print(f"            →  {out.name}")

        t0 = time.time()
        success = process_file(src, out, args)
        elapsed = time.time() - t0

        if success:
            size_mb = out.stat().st_size / 1_048_576
            print(f"            ✓  Done  ({fmt_time(elapsed)}, {size_mb:.1f} MB)\n")
            ok_list.append(src.name)
        else:
            print(f"            ✗  FAILED\n")
            fail_list.append(src.name)

    # ── Summary ───────────────────────────────────────────────────────────
    total_time = time.time() - batch_start
    print(f"\n{'='*60}")
    print(f"  Batch Summary  ({fmt_time(total_time)} total)")
    print(f"{'='*60}")
    print(f"  Succeeded : {len(ok_list)}")
    print(f"  Failed    : {len(fail_list)}")
    if skip_list:
        print(f"  Skipped   : {len(skip_list)}")

    if fail_list:
        print("\n  Failed files:")
        for name in fail_list:
            print(f"    - {name}")

    # ── Write log ─────────────────────────────────────────────────────────
    log_path = output_dir / "batch_log.txt"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Batch Upscale Log\n")
        f.write(f"Input  : {input_dir}\n")
        f.write(f"Output : {output_dir}\n")
        f.write(f"Target : {args.target}  Mode: {args.mode}\n\n")
        f.write(f"Succeeded ({len(ok_list)}):\n")
        for name in ok_list:
            f.write(f"  OK    {name}\n")
        if fail_list:
            f.write(f"\nFailed ({len(fail_list)}):\n")
            for name in fail_list:
                f.write(f"  FAIL  {name}\n")
        if skip_list:
            f.write(f"\nSkipped ({len(skip_list)}):\n")
            for name in skip_list:
                f.write(f"  SKIP  {name}\n")

    print(f"\n  Log saved: {log_path}\n")


if __name__ == "__main__":
    main()
