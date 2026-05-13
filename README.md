# 影片超解析度放大工具

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
| GPU | 選用（AI 模式有 GPU 快 10 倍） |

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

**方式 A（推薦）：** 開啟 GUI 後點選「安裝 AI 套件」按鈕

**方式 B：** 執行資料夾內的批次檔：

```powershell
install_ai.bat
```

安裝項目：`torch`、`realesrgan`、`basicsr`、`opencv-python`

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
| 安裝 AI 套件 | 一鍵安裝 Real-ESRGAN 所有依賴 |
| 轉換進度 | 即時顯示整體與單一檔案的百分比、FPS、速度、剩餘時間 |
| 執行日誌 | 詳細記錄每個步驟的輸出 |

**進度面板說明：**

```
轉換進度
整體： ████████████░░░░░░░  60%   3 / 5 個檔案
       PITAZO_ENERO_12_2015.mp4
目前： ████████████████░░░  78%
       43 fps   速度 ×1.4   剩餘 00:45
```

- **整體進度**：顯示批次中已完成的檔案數與百分比
- **目前進度**：顯示目前正在處理的單一檔案進度
- **統計資訊**：FPS（每秒處理幀數）、處理速度倍率、剩餘時間

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

先查詢 CUDA 版本：

```powershell
nvidia-smi
```

至 [https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/) 選擇對應版本，例如 CUDA 12.1：

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

安裝後在 `upscale.py` 內將 `half=False` 改為 `half=True` 可進一步加速。

---

## 輸出規格

- 影片編碼：H.264（libx264），CRF 18（接近無損品質）
- 編碼速度：preset medium（速度與品質的最佳平衡）
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

**AI 模式跑很慢**
→ 沒有 GPU 時每幀約需 5～30 秒，長影片需耐心等候；可先用快速模式測試流程。

**記憶體不足（OOM）**
→ `upscale.py` 已啟用 `tile=512` 分塊處理，若仍不足可將此值改小（如 `256`）。

**GUI 無法開啟**
→ 確認 Python 已安裝並加入 PATH；或在終端機直接執行 `python launcher.py`。

**輸出檔案無法播放**
→ 確認轉換有正常完成（不要在轉換中途讀取輸出檔）。程式已加入 `-movflags +faststart` 與失敗自動清理，正常完成的檔案可在所有主流播放器播放。

**檔案被程式鎖住無法刪除**
→ 使用 `force_delete.bat` 強制解鎖並刪除（見上方說明）。

---

## 檔案結構

```
video/
├── start.bat           # 雙擊開啟 GUI（一般使用者入口）
├── launcher.py         # GUI 圖形介面主程式（含即時進度顯示）
├── upscale.py          # 單一影片命令列工具
├── batch_upscale.py    # 批次轉檔命令列工具
├── force_delete.bat    # 強制刪除啟動器（拖曳或雙擊使用）
├── force_delete.ps1    # 強制刪除邏輯（重試 + 重開機排程）
├── install_ai.bat      # AI 套件一鍵安裝（命令列版）
└── README.md           # 本說明文件
```
