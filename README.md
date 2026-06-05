# 影片超解析度放大工具

[English](README.en.md) | 繁體中文

將低解析度影片（如 640×480）升級為高清畫質（720p / 1080p / 4K），提供三種使用方式：

| 使用方式 | 說明 | 適合對象 |
|----------|------|----------|
| `start.bat` 雙擊啟動 | 圖形介面，含所有功能與即時進度 | 一般使用者 |
| `batch_upscale.py` | 命令列批次轉檔 | 進階 / 自動化 |
| `upscale.py` | 命令列單一影片 | 進階 / 腳本整合 |

---

## 系統需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Windows 10 / 11 |
| Python | 3.8 以上 |
| FFmpeg | 見安裝步驟 |
| psutil | 隨 Python 自動安裝 |
| GPU | 選用（AI 模式有 GPU 快 10 倍以上） |

---

## 安裝

### Step 1：安裝 FFmpeg（必要）

開啟 PowerShell，執行：

```powershell
winget install --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
```

安裝後**重新開啟**終端機讓 PATH 生效。程式會自動從 Windows Registry 尋找 FFmpeg，即使 PATH 尚未更新也能正常運作。

### Step 2：安裝 psutil（建議）

用於關閉視窗時正確終止所有子程序：

```powershell
pip install psutil
```

### Step 3：安裝 AI 套件（AI 模式才需要）

**方式 A（推薦）：** 開啟 GUI 後點選「安裝 AI 套件」按鈕，程式會自動偵測 NVIDIA 顯卡並安裝正確的 CUDA 版本。

**方式 B：** 執行資料夾內的批次檔：

```powershell
install_ai.bat
```

安裝項目：`torch`（CUDA 12.8 版，支援 RTX 5000/4000 系列）、`realesrgan`、`basicsr`、`opencv-python`

---

## 使用方式

### 方式一：GUI 圖形介面（最簡單）

直接雙擊 `start.bat` 即可開啟圖形介面。

**介面功能說明：**

| 區塊 | 功能 |
|------|------|
| 處理模式 | 切換「單一影片」或「批次轉檔（整個資料夾）」 |
| 路徑設定 | 選擇輸入影片/資料夾與輸出位置 |
| 目標解析度 | 480p / 720p / 1080p / 1440p / 4k |
| 處理方式 | 快速 Lanczos 或 AI 超解析 |
| 包含子資料夾 | 批次模式下是否遞迴搜尋 |
| 安裝 AI 套件 | 一鍵安裝 Real-ESRGAN 所有依賴，自動選擇 CPU / CUDA 版本 |
| GPU 狀態列 | 啟動時自動偵測 GPU 與 PyTorch 版本，若有問題顯示修復按鈕 |
| 語系切換 | 標題列右上角按鈕，中英文即時切換 |
| 轉換進度 | 即時顯示整體與單一檔案的百分比、FPS、速度、剩餘時間 |
| 執行日誌 | 詳細記錄每個步驟的輸出 |

**進度面板說明：**

```
轉換進度
整體： ████████████░░░░░░░  60%   3 / 5 個檔案
       PITAZO_ENERO_12_2015.mp4
目前： ████████████████░░░  78%
       43 幀/秒   AI 處理中   剩餘 00:45
```

---

### 方式二：命令列 — 單一影片

```powershell
# 基本用法：640x480 → 1080p（快速模式）
python upscale.py input.mp4 --target 1080p

# 指定輸出檔名
python upscale.py input.mp4 output_hd.mp4 --target 1080p

# AI 超解析模式
python upscale.py input.mp4 --target 1080p --mode ai

# 放大到 4K
python upscale.py input.mp4 --target 4k --mode ai

# 自訂解析度
python upscale.py input.mp4 --target 1920x1080
```

**所有參數：**

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `input` | 必填 | 輸入影片路徑 |
| `output` | 自動產生 `_upscaled` | 輸出影片路徑 |
| `--target` | `1080p` | 目標解析度（480p / 720p / 1080p / 1440p / 4k / WxH） |
| `--mode` | `simple` | `simple`（Lanczos）或 `ai`（Real-ESRGAN） |
| `--model` | `RealESRGAN_x4plus` | AI 模型（ai 模式適用） |

---

### 方式三：命令列 — 批次轉檔

```powershell
# 資料夾內所有影片 → 1080p（輸出至 ./raw_videos/upscaled/）
python batch_upscale.py ./raw_videos --target 1080p

# 指定輸出資料夾
python batch_upscale.py ./raw_videos ./output --target 1080p

# AI 模式批次放大到 4K
python batch_upscale.py ./raw_videos ./output --mode ai --target 4k

# 包含子資料夾，跳過已存在的輸出檔
python batch_upscale.py ./raw_videos --recursive --skip-existing
```

**所有參數：**

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `input_dir` | 必填 | 輸入資料夾路徑 |
| `output_dir` | `input_dir/upscaled` | 輸出資料夾 |
| `--target` | `1080p` | 目標解析度 |
| `--mode` | `simple` | 處理方式 |
| `--model` | `RealESRGAN_x4plus` | AI 模型 |
| `--recursive` / `-r` | 否 | 搜尋子資料夾 |
| `--skip-existing` | 否 | 跳過已存在的輸出檔 |

批次處理結束後會在輸出資料夾產生 `batch_log.txt`，記錄每個檔案的成功/失敗狀態。

---

## 兩種處理方式比較

| | Simple（Lanczos） | AI（Real-ESRGAN） |
|---|---|---|
| 速度 | 秒～分鐘 | 分鐘～數小時 |
| 品質 | 畫面放大，邊緣稍銳利 | AI 補充真實紋理，細節明顯更好 |
| GPU | 不需要 | 選用（有 GPU 快很多） |
| 安裝 | 直接可用 | 需安裝 AI 套件 |
| 適合 | 快速預覽、大量批次 | 最終成品輸出 |

## AI 模型說明

| 模型 | 放大倍數 | 適合內容 |
|------|----------|----------|
| `RealESRGAN_x4plus` | 4× | 真實場景、人臉、自然景物（預設） |
| `RealESRGAN_x2plus` | 2× | 原始畫質較好、只需少量放大 |

---

## GPU 加速（NVIDIA 顯示卡）

### 自動安裝（推薦）

開啟 GUI 後點選「安裝 AI 套件」，程式會自動偵測 NVIDIA 顯卡，安裝支援 RTX 5000/4000 系列的 **CUDA 12.8** 版 PyTorch。

### 手動安裝

```powershell
# CUDA 12.8（支援 RTX 5000 Blackwell、RTX 4000 Ada 系列）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

安裝後執行以下指令驗證：

```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0))"
```

### GPU 狀態列

GUI 啟動時自動偵測並顯示：

| 顯示 | 說明 |
|------|------|
| 🟢 `GPU 就緒：RTX 5060   PyTorch 2.x.x+cu128` | 一切正常，AI 模式使用 GPU |
| 🔴 `警告：偵測到 NVIDIA GPU 但 PyTorch 是 CPU 版...` | 裝了 CPU 版，出現**一鍵修復**按鈕 |
| ⚫ `未偵測到 NVIDIA GPU` | 無 NVIDIA 顯卡，AI 模式使用 CPU |

### AI 模式 GPU 效能優化

| 優化 | 說明 |
|------|------|
| NVENC 硬體編碼 | 自動偵測，有 NVIDIA GPU 時用 GPU 編碼取代 CPU libx264 |
| 執行緒 I/O 流水線 | 讀幀 / GPU 推論 / 寫幀三個執行緒並行，GPU 使用率大幅提升 |
| VRAM 自動 Tile | 依顯卡 VRAM 自動選擇分塊大小（≥10 GB 不分塊，最快） |
| FP16 推論 | GPU 模式自動啟用半精度，速度提升約 2 倍 |

---

## 輸出規格

- 影片編碼：有 NVIDIA GPU 時使用 h264_nvenc（GPU 硬體），否則 libx264（CRF 18）
- 編碼速度：nvenc preset p4 / libx264 preset medium
- MP4 結構：moov atom 置於檔頭（`-movflags +faststart`），確保各播放器相容
- 音訊：直接複製原始音軌，不重新編碼
- 容器格式：與輸入相同（.mp4 → .mp4）

---

## 強制刪除被鎖住的檔案

轉檔中途停止時，輸出中的 mp4 可能被 FFmpeg 程序鎖住而無法刪除。

使用 `force_delete.bat` 解除鎖定並刪除（實際邏輯由 `force_delete.ps1` 執行）：

**方式 A：拖曳刪除**
將要刪除的 mp4 檔案直接**拖曳到 `force_delete.bat` 上面放開**（支援多選）。

**方式 B：雙擊選檔**
雙擊 `force_delete.bat`，在彈出的視窗中選擇要刪除的檔案（`Ctrl` 多選）。

程式會依序執行：
1. 強制終止所有 `ffmpeg.exe`、`ffprobe.exe`
2. 終止執行 `upscale.py` 的 Python 程序
3. 等待 3 秒讓 OS 釋放檔案控制代碼
4. 以 PowerShell 強制刪除，最多**重試 5 次**（每次間隔 1 秒）
5. 若仍無法刪除 → 自動透過 Windows `MoveFileEx` API **排程下次重開機時刪除**

**執行結果說明：**

| 狀態 | 意義 |
|------|------|
| `[OK]` | 已立即刪除 |
| `[REBOOT]` | 重開機後自動刪除，無需再操作 |
| `[FAIL]` | 右鍵 `force_delete.bat` → 以系統管理員身分執行後再試 |

---

## 疑難排解

**`ffmpeg not found` 錯誤**
→ 程式會自動從 Windows Registry 搜尋 FFmpeg 路徑，通常不需手動設定 PATH。若仍出現此錯誤，請重新安裝 FFmpeg。

**`ModuleNotFoundError: realesrgan`**
→ 尚未安裝 AI 套件，點選 GUI 內「安裝 AI 套件」或執行 `install_ai.bat`。

**AI 模式 CPU 和 GPU 都吃很兇，但 GPU 只有 5% 以下**
→ PyTorch 裝的是 CPU 版，AI 推論完全跑在 CPU。GUI 啟動時的 GPU 狀態列若顯示紅色警告，點選**一鍵修復**重新安裝 CUDA 版本。或手動執行：
```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 --force-reinstall
```
安裝完重啟程式，GPU 使用率應明顯上升。

**AI 模式跑很慢（無 GPU）**
→ 沒有 GPU 時每幀約需 5～30 秒，長影片需耐心等候；可先用快速模式測試流程。

**記憶體不足（OOM）**
→ `upscale.py` 已依 VRAM 自動選擇分塊大小。若仍不足，可在 `upscale_ai()` 中手動將 tile 值改為 `256` 或更小。

**GUI 無法開啟**
→ 確認 Python 已安裝並加入 PATH；或在終端機直接執行 `python launcher.py`。

**輸出檔案無法播放**
→ 確認轉換有正常完成（不要在轉換中途讀取輸出檔）。程式已加入 `-movflags +faststart` 與失敗自動清理，正常完成的檔案可在所有主流播放器播放。

**檔案被程式鎖住無法刪除**
→ 使用 `force_delete.bat` 強制解鎖並刪除（見上方說明）。

---

## 測試

執行所有單元測試與整合測試：

```powershell
python -m unittest test_upscale -v
```

測試涵蓋範圍（82 個測試案例，73 通過 + 9 跳過需 test_clip.mp4）：

| 模組 | 測試類別 | 說明 |
|------|----------|------|
| `upscale.py` | `TestParseTime` | 時間字串解析（時/分/秒/小數） |
| `upscale.py` | `TestResolveTarget` | 解析度轉換與比例計算 |
| `upscale.py` | `TestCleanup` | 不完整輸出檔清理 |
| `upscale.py` | `TestFindFfmpeg` | FFmpeg 路徑偵測 |
| `upscale.py` | `TestCheckNvenc` | NVENC 編碼器偵測（mock） |
| `upscale.py` | `TestEncoderArgs` | GPU / CPU 編碼器參數生成 |
| `upscale.py` | `TestAutoTileSize` | VRAM 自動 Tile 大小選擇 |
| `upscale.py` | `TestUpscaleFramesThreaded` | 執行緒 I/O 流水線（需 opencv） |
| `upscale.py` | `TestGetVideoInfo` | 影片資訊讀取（需 ffprobe + test_clip.mp4） |
| `upscale.py` | `TestUpscaleSimple` | Lanczos 轉檔整合測試（需 ffmpeg） |
| `batch_upscale.py` | `TestFmtTime` | 時間格式化 |
| `batch_upscale.py` | `TestProcessFile` | 子程序呼叫邏輯（mock） |
| `launcher.py` | `TestFmtEta` | GUI 倒數時間格式化 |
| `launcher.py` | `TestLangStructure` | 翻譯字典完整性與佔位符一致性 |

整合測試需要 `test_clip.mp4`（5 秒測試短片），可從任意影片擷取。

---

## 已知相容性修補

安裝 AI 套件後若遇到以下錯誤，程式已自動修補（首次安裝時需手動執行一次）：

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

## 檔案結構

```
video/
├── start.bat           # 雙擊開啟 GUI（一般使用者入口）
├── launcher.py         # GUI 圖形介面主程式（含即時進度、語系切換、GPU 狀態）
├── upscale.py          # 單一影片命令列工具
├── batch_upscale.py    # 批次轉檔命令列工具
├── test_upscale.py     # 單元測試與整合測試（82 個測試案例）
├── force_delete.bat    # 強制刪除啟動器（拖曳或雙擊使用）
├── force_delete.ps1    # 強制刪除邏輯（重試 + 重開機排程）
├── install_ai.bat      # AI 套件一鍵安裝（命令列版）
├── README.md           # 本說明文件（繁體中文）
└── README.en.md        # 本說明文件（English）
```
