# Video Super-Resolution Upscaler

繁體中文 | [English](README.en.md)

Upscale low-resolution videos (e.g. 640×480) to HD quality (720p / 1080p / 4K) using three interfaces:

| Interface | Description | Best for |
|-----------|-------------|----------|
| `start.bat` double-click | GUI with all features and live progress | General users |
| `batch_upscale.py` | CLI batch processing | Advanced / automation |
| `upscale.py` | CLI single-file | Advanced / scripting |

---

## Requirements

| Item | Requirement |
|------|-------------|
| OS | Windows 10 / 11 |
| Python | 3.8 or higher |
| FFmpeg | See installation steps |
| psutil | Installed automatically with Python |
| GPU | Optional (AI mode is ~10× faster with GPU) |

---

## Installation

### Step 1: Install FFmpeg (required)

Open PowerShell and run:

```powershell
winget install --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
```

**Reopen** the terminal after installation for the PATH to take effect. The tool automatically searches for FFmpeg in the Windows Registry, so it works even if PATH has not been refreshed yet.

### Step 2: Install psutil (recommended)

Used to correctly terminate all child processes when the window is closed:

```powershell
pip install psutil
```

### Step 3: Install AI packages (AI mode only)

**Option A (recommended):** Open the GUI and click the **"Install AI Packages"** button. The installer automatically detects your NVIDIA GPU and installs the correct CUDA build.

**Option B:** Run the batch file in the project folder:

```powershell
install_ai.bat
```

Packages installed: `torch` (CUDA 12.8 build, supports RTX 5000/4000 series), `realesrgan`, `basicsr`, `opencv-python`

---

## Usage

### Option 1: GUI (easiest)

Double-click `start.bat` to open the graphical interface.

**UI sections:**

| Section | Description |
|---------|-------------|
| Processing mode | Switch between "Single file" and "Batch folder" |
| Paths | Select input video/folder and output location |
| Target resolution | 480p / 720p / 1080p / 1440p / 4K |
| Method | Fast Lanczos or AI Super-Resolution |
| Include subfolders | Recursive search in batch mode |
| Install AI packages | One-click install with auto GPU/CPU detection |
| GPU status bar | Detects GPU and PyTorch version at startup; shows a fix button if misconfigured |
| Language switcher | Button in the top-right header; switches between English and 中文 instantly |
| Progress panel | Live percentage, FPS, speed, and ETA |
| Execution log | Detailed step-by-step output |

**Progress panel example:**

```
Progress
Overall: ████████████░░░░░░░  60%   3 / 5 files
         PITAZO_ENERO_12_2015.mp4
Current: ████████████████░░░  78%
         43 fps   AI processing   ETA 00:45
```

---

### Option 2: CLI — Single file

```powershell
# Basic: 640x480 → 1080p (fast mode)
python upscale.py input.mp4 --target 1080p

# Specify output filename
python upscale.py input.mp4 output_hd.mp4 --target 1080p

# AI super-resolution mode
python upscale.py input.mp4 --target 1080p --mode ai

# Upscale to 4K
python upscale.py input.mp4 --target 4k --mode ai

# Custom resolution
python upscale.py input.mp4 --target 1920x1080
```

**All arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `input` | required | Input video path |
| `output` | auto-generated `_upscaled` | Output video path |
| `--target` | `1080p` | Target resolution (480p / 720p / 1080p / 1440p / 4k / WxH) |
| `--mode` | `simple` | `simple` (Lanczos) or `ai` (Real-ESRGAN) |
| `--model` | `RealESRGAN_x4plus` | AI model (ai mode only) |

---

### Option 3: CLI — Batch processing

```powershell
# All videos in a folder → 1080p (output to ./raw_videos/upscaled/)
python batch_upscale.py ./raw_videos --target 1080p

# Specify output folder
python batch_upscale.py ./raw_videos ./output --target 1080p

# AI mode batch upscale to 4K
python batch_upscale.py ./raw_videos ./output --mode ai --target 4k

# Include subfolders, skip already-converted files
python batch_upscale.py ./raw_videos --recursive --skip-existing
```

**All arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `input_dir` | required | Input folder path |
| `output_dir` | `input_dir/upscaled` | Output folder |
| `--target` | `1080p` | Target resolution |
| `--mode` | `simple` | Processing method |
| `--model` | `RealESRGAN_x4plus` | AI model |
| `--recursive` / `-r` | off | Search subfolders recursively |
| `--skip-existing` | off | Skip files already present in output folder |

A `batch_log.txt` is written to the output folder after each run recording success/failure per file.

---

## Method Comparison

| | Simple (Lanczos) | AI (Real-ESRGAN) |
|---|---|---|
| Speed | Seconds to minutes | Minutes to hours |
| Quality | Enlarged with slightly sharper edges | AI-reconstructed textures, noticeably better detail |
| GPU | Not required | Optional (much faster with GPU) |
| Setup | Ready to use | Requires AI packages |
| Best for | Quick preview, large batch jobs | Final output quality |

## AI Models

| Model | Scale | Best for |
|-------|-------|----------|
| `RealESRGAN_x4plus` | 4× | Real-world footage, faces, natural scenes (default) |
| `RealESRGAN_x2plus` | 2× | Source with decent quality needing only a small boost |

---

## GPU Acceleration (NVIDIA)

### Automatic install (recommended)

Open the GUI and click **"Install AI Packages"**. The installer detects your NVIDIA GPU and installs **CUDA 12.8** PyTorch, which supports the RTX 5000 (Blackwell) and RTX 4000 (Ada) series.

### Manual install

```powershell
# CUDA 12.8 — supports RTX 5000 Blackwell and RTX 4000 Ada series
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

Verify the installation:

```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0))"
```

### GPU status bar

The GUI automatically detects and displays GPU status at startup:

| Display | Meaning |
|---------|---------|
| 🟢 `GPU Ready: RTX 5060   PyTorch 2.x.x+cu128` | All good — AI mode uses GPU |
| 🔴 `Warning: NVIDIA GPU detected but PyTorch is CPU build...` | CPU build installed — a **One-Click Fix** button appears |
| ⚫ `No NVIDIA GPU detected` | No NVIDIA card — AI mode uses CPU |

### AI mode GPU performance optimizations

| Optimization | Description |
|---|---|
| NVENC hardware encoding | Auto-detected; uses GPU encoder instead of CPU libx264 when NVIDIA GPU is available |
| Threaded I/O pipeline | Frame read / GPU inference / frame write run in parallel threads — GPU stays busy |
| Auto tile size by VRAM | Tile size selected automatically (≥10 GB VRAM = no tiling, fastest) |
| FP16 inference | Half-precision enabled automatically in GPU mode — ~2× speed boost |

---

## Output Specs

- Video codec: `h264_nvenc` (GPU hardware, when NVIDIA available) or `libx264` CRF 18 (CPU)
- Encoding preset: nvenc `p4` / libx264 `medium`
- MP4 structure: moov atom at front (`-movflags +faststart`) for broad player compatibility
- Audio: copied from source without re-encoding
- Container: matches input (.mp4 → .mp4)

---

## Force-Delete Locked Files

If encoding is stopped mid-way, the output `.mp4` may be locked by FFmpeg and cannot be deleted normally.

Use `force_delete.bat` to unlock and remove it (logic handled by `force_delete.ps1`):

**Option A: Drag and drop**
Drag the locked `.mp4` file(s) **onto `force_delete.bat`** and release (multi-select supported).

**Option B: Double-click and pick**
Double-click `force_delete.bat` and select the file(s) in the dialog (`Ctrl` for multi-select).

The script runs in sequence:
1. Force-terminate all `ffmpeg.exe` and `ffprobe.exe` processes
2. Terminate any Python process running `upscale.py`
3. Wait 3 seconds for the OS to release file handles
4. Force-delete via PowerShell, retrying up to **5 times** (1 second apart)
5. If still locked → schedule deletion via Windows `MoveFileEx` API **on next reboot**

**Status codes:**

| Status | Meaning |
|--------|---------|
| `[OK]` | Deleted immediately |
| `[REBOOT]` | Will be deleted automatically on next reboot |
| `[FAIL]` | Right-click `force_delete.bat` → Run as Administrator and retry |

---

## Troubleshooting

**`ffmpeg not found` error**
→ The tool searches the Windows Registry automatically. If the error persists, reinstall FFmpeg.

**`ModuleNotFoundError: realesrgan`**
→ AI packages not installed. Click "Install AI Packages" in the GUI or run `install_ai.bat`.

**AI mode hammers CPU at 99% but GPU stays at 0–5%**
→ A CPU build of PyTorch is installed — AI inference runs entirely on CPU. If the GPU status bar shows a red warning, click **One-Click Fix** to reinstall the CUDA build. Or run manually:
```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 --force-reinstall
```
Restart the app after installation; GPU utilization should rise significantly.

**AI mode is very slow (no GPU)**
→ Without a GPU, each frame takes 5–30 seconds. Long videos require patience; use fast mode first to verify the workflow.

**Out of memory (OOM)**
→ Tile size is selected automatically based on VRAM. If OOM persists, manually set a smaller tile value (e.g. `256`) in `upscale_ai()`.

**GUI won't open**
→ Confirm Python is installed and in PATH; or run `python launcher.py` directly from the terminal.

**Output file won't play**
→ Ensure the conversion completed normally (do not read the output file while encoding). Successfully completed files include `-movflags +faststart` and are playable in all major players.

**File locked and cannot be deleted**
→ Use `force_delete.bat` (see above).

---

## Testing

Run all unit and integration tests:

```powershell
python -m unittest test_upscale -v
```

Test coverage (82 test cases — 73 pass + 9 skip requiring `test_clip.mp4`):

| Module | Test class | Description |
|--------|------------|-------------|
| `upscale.py` | `TestParseTime` | Time string parsing (h/m/s/fractions) |
| `upscale.py` | `TestResolveTarget` | Resolution conversion and scale factor |
| `upscale.py` | `TestCleanup` | Incomplete output file removal |
| `upscale.py` | `TestFindFfmpeg` | FFmpeg path detection |
| `upscale.py` | `TestCheckNvenc` | NVENC encoder detection (mocked) |
| `upscale.py` | `TestEncoderArgs` | GPU / CPU encoder argument generation |
| `upscale.py` | `TestAutoTileSize` | VRAM-based auto tile size selection |
| `upscale.py` | `TestUpscaleFramesThreaded` | Threaded I/O pipeline (requires opencv) |
| `upscale.py` | `TestGetVideoInfo` | Video info extraction (requires ffprobe + test_clip.mp4) |
| `upscale.py` | `TestUpscaleSimple` | Lanczos upscale integration test (requires ffmpeg) |
| `batch_upscale.py` | `TestFmtTime` | Time formatting |
| `batch_upscale.py` | `TestProcessFile` | Subprocess invocation logic (mocked) |
| `launcher.py` | `TestFmtEta` | GUI countdown time formatting |
| `launcher.py` | `TestLangStructure` | Translation dict completeness and placeholder consistency |

Integration tests require `test_clip.mp4` (a short 5-second clip extracted from any video).

---

## Compatibility Patches

After installing the AI packages, you may encounter the following error on Python 3.11+. Apply the one-time patch below:

**`ModuleNotFoundError: torchvision.transforms.functional_tensor`**

```powershell
python -c "
import site, pathlib
p = pathlib.Path(site.getsitepackages()[0]) / 'basicsr/data/degradations.py'
p.write_text(p.read_text().replace(
    'from torchvision.transforms.functional_tensor import rgb_to_grayscale',
    'from torchvision.transforms.functional import rgb_to_grayscale'
))
print('patched:', p)
"
```

---

## File Structure

```
video/
├── start.bat           # Double-click to open GUI (entry point for general users)
├── launcher.py         # GUI main application (live progress, language switcher, GPU status)
├── upscale.py          # Single-file CLI tool
├── batch_upscale.py    # Batch processing CLI tool
├── test_upscale.py     # Unit and integration tests (82 test cases)
├── force_delete.bat    # Force-delete launcher (drag-and-drop or double-click)
├── force_delete.ps1    # Force-delete logic (retry + reboot scheduling)
├── install_ai.bat      # One-click AI package installer (CLI version)
├── README.md           # This document (Traditional Chinese)
└── README.en.md        # This document (English)
```
