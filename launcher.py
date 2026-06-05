"""
Video Upscaler GUI Launcher
One-click interface for single and batch upscaling.
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import subprocess
import sys
import os
import queue
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
UPSCALE_PY  = SCRIPT_DIR / "upscale.py"
PYTHON      = sys.executable

VIDEO_EXTS  = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".mts", ".mpg", ".mpeg"}
TARGET_OPTS = ["480p", "720p", "1080p", "1440p", "4k"]
MODEL_OPTS  = ["RealESRGAN_x4plus", "RealESRGAN_x2plus"]

# ── Translations ───────────────────────────────────────────────────────────────
LANGS: dict[str, dict[str, str]] = {
    "zh": {
        "title":                "影片超解析度放大工具",
        "header":               "影片超解析度放大工具",
        "lang_btn":             "English",
        # Mode
        "mode_frame":           "處理模式",
        "mode_single":          "單一影片",
        "mode_batch":           "批次轉檔（整個資料夾）",
        # Paths
        "path_frame":           "路徑設定",
        "input_video":          "輸入影片：",
        "input_folder":         "輸入資料夾：",
        "output_path":          "輸出位置：",
        "browse":               "瀏覽",
        "include_sub":          "包含子資料夾",
        # Settings
        "settings_frame":       "轉換設定",
        "target_res":           "目標解析度：",
        "method":               "處理方式：",
        "method_simple":        "快速 Lanczos",
        "method_ai":            "AI 超解析 (Real-ESRGAN)",
        "ai_model":             "AI 模型：",
        # Buttons
        "btn_start":            "▶  開始轉換",
        "btn_stop":             "■  停止",
        "btn_install":          "安裝 AI 套件",
        "btn_clear":            "清除日誌",
        "btn_gpu_fix":          "一鍵修復（安裝 GPU 版）",
        # GPU status bar
        "gpu_detecting":        "正在偵測 GPU...",
        "gpu_ready":            "GPU 就緒：{name}   PyTorch {ver}",
        "gpu_cpu_build":        "警告：偵測到 NVIDIA GPU 但 PyTorch 是 CPU 版（{ver}），AI 模式將使用 CPU（非常慢）",
        "gpu_cuda_fail":        "警告：NVIDIA GPU 存在但 CUDA 無法啟動（{ver}），請重新安裝 GPU 版套件",
        "gpu_no_nvidia":        "未偵測到 NVIDIA GPU，AI 模式將使用 CPU   PyTorch {ver}",
        "gpu_unknown":          "PyTorch {ver}（未安裝或無 CUDA）",
        "gpu_not_installed":    "（未安裝）",
        # Progress panel
        "progress_frame":       "轉換進度",
        "overall":              "整體：",
        "current":              "目前：",
        "ready":                "準備中…",
        # Log panel
        "log_frame":            "執行日誌",
        # Stats line
        "fps_unit":             "幀/秒",
        "ai_processing":        "AI 處理中",
        "remaining":            "剩餘",
        "speed_x":              "速度 ×",
        # Dialogs
        "dlg_error":            "錯誤",
        "dlg_warn":             "提示",
        "dlg_install_title":    "安裝 AI 套件",
        "dlg_install_body":     (
            "將安裝以下套件（約需 3–10 分鐘）：\n\n"
            "  • torch + torchvision（自動偵測 GPU，有 NVIDIA 裝 CUDA 版）\n"
            "  • realesrgan\n  • basicsr\n  • opencv-python\n\n"
            "是否繼續？"
        ),
        "dlg_need_folder":      "請先選擇資料夾",
        "dlg_need_video":       "請先選擇影片檔案",
        "dlg_path_missing":     "路徑不存在：{path}",
        "dlg_script_missing":   "找不到 upscale.py，請確認與 launcher.py 在同一資料夾",
        "dlg_browse_in_folder": "選擇輸入資料夾",
        "dlg_browse_in_video":  "選擇影片檔案",
        "dlg_browse_out_folder":"選擇輸出資料夾",
        "dlg_browse_out_video": "另存輸出影片",
        "dlg_video_files":      "影片檔案",
        "dlg_all_files":        "所有檔案",
        "dlg_mp4_files":        "MP4 影片",
        # Log messages
        "log_stopped":          "已由使用者停止",
        "log_no_videos":        "資料夾內找不到影片檔案",
        "log_found":            "找到 {n} 個影片，輸出至：{path}",
        "log_done":             "  完成：{name}",
        "log_failed":           "  失敗：{err}",
        "log_batch_done":       "\n批次完成 — 成功 {ok} 個，失敗 {fail} 個",
        "log_proc_error":       "程式錯誤（returncode={rc}）",
        "log_unexpected":       "未預期錯誤：{err}",
        "log_installing_cuda":  "偵測到 NVIDIA GPU，安裝 CUDA 12.8 版 PyTorch（支援 RTX 5000/4000 系列）...",
        "log_installing_cpu":   "未偵測到 NVIDIA GPU，安裝 CPU 版 PyTorch（速度較慢）",
        "log_install_done":     "\nAI 套件安裝完成！",
        "log_install_fail":     "安裝失敗：{err}",
        # State helpers
        "state_processing":     "處理中...",
        "state_installing":     "安裝 AI 套件中...",
        "state_done":           "全部完成",
        "state_stopped":        "已停止",
        "state_files":          "{done} / {total} 個檔案",
    },
    "en": {
        "title":                "Video Super-Resolution Upscaler",
        "header":               "Video Super-Resolution Upscaler",
        "lang_btn":             "中文",
        # Mode
        "mode_frame":           "Mode",
        "mode_single":          "Single File",
        "mode_batch":           "Batch (Entire Folder)",
        # Paths
        "path_frame":           "Paths",
        "input_video":          "Input Video:",
        "input_folder":         "Input Folder:",
        "output_path":          "Output Path:",
        "browse":               "Browse",
        "include_sub":          "Include Subfolders",
        # Settings
        "settings_frame":       "Settings",
        "target_res":           "Target Resolution:",
        "method":               "Method:",
        "method_simple":        "Fast Lanczos",
        "method_ai":            "AI Upscale (Real-ESRGAN)",
        "ai_model":             "AI Model:",
        # Buttons
        "btn_start":            "▶  Start",
        "btn_stop":             "■  Stop",
        "btn_install":          "Install AI Packages",
        "btn_clear":            "Clear Log",
        "btn_gpu_fix":          "One-Click Fix (Install GPU Build)",
        # GPU status bar
        "gpu_detecting":        "Detecting GPU...",
        "gpu_ready":            "GPU Ready: {name}   PyTorch {ver}",
        "gpu_cpu_build":        "Warning: NVIDIA GPU detected but PyTorch is CPU build ({ver}). AI mode will use CPU (very slow)",
        "gpu_cuda_fail":        "Warning: NVIDIA GPU present but CUDA cannot start ({ver}). Please reinstall GPU packages",
        "gpu_no_nvidia":        "No NVIDIA GPU detected. AI mode will use CPU   PyTorch {ver}",
        "gpu_unknown":          "PyTorch {ver} (not installed or no CUDA)",
        "gpu_not_installed":    "(not installed)",
        # Progress panel
        "progress_frame":       "Progress",
        "overall":              "Overall:",
        "current":              "Current:",
        "ready":                "Preparing…",
        # Log panel
        "log_frame":            "Log",
        # Stats line
        "fps_unit":             "fps",
        "ai_processing":        "AI processing",
        "remaining":            "ETA",
        "speed_x":              "Speed ×",
        # Dialogs
        "dlg_error":            "Error",
        "dlg_warn":             "Notice",
        "dlg_install_title":    "Install AI Packages",
        "dlg_install_body":     (
            "The following packages will be installed (3–10 min):\n\n"
            "  • torch + torchvision (auto-detects GPU, installs CUDA build for NVIDIA)\n"
            "  • realesrgan\n  • basicsr\n  • opencv-python\n\n"
            "Continue?"
        ),
        "dlg_need_folder":      "Please select a folder first",
        "dlg_need_video":       "Please select a video file first",
        "dlg_path_missing":     "Path not found: {path}",
        "dlg_script_missing":   "upscale.py not found. Make sure it is in the same folder as launcher.py",
        "dlg_browse_in_folder": "Select Input Folder",
        "dlg_browse_in_video":  "Select Video File",
        "dlg_browse_out_folder":"Select Output Folder",
        "dlg_browse_out_video": "Save Output Video",
        "dlg_video_files":      "Video Files",
        "dlg_all_files":        "All Files",
        "dlg_mp4_files":        "MP4 Video",
        # Log messages
        "log_stopped":          "Stopped by user",
        "log_no_videos":        "No video files found in folder",
        "log_found":            "Found {n} videos, output to: {path}",
        "log_done":             "  Done: {name}",
        "log_failed":           "  Failed: {err}",
        "log_batch_done":       "\nBatch complete — {ok} succeeded, {fail} failed",
        "log_proc_error":       "Process error (returncode={rc})",
        "log_unexpected":       "Unexpected error: {err}",
        "log_installing_cuda":  "NVIDIA GPU detected. Installing CUDA 12.8 PyTorch (supports RTX 5000/4000)...",
        "log_installing_cpu":   "No NVIDIA GPU detected. Installing CPU PyTorch (slower)",
        "log_install_done":     "\nAI packages installed!",
        "log_install_fail":     "Installation failed: {err}",
        # State helpers
        "state_processing":     "Processing...",
        "state_installing":     "Installing AI packages...",
        "state_done":           "All done",
        "state_stopped":        "Stopped",
        "state_files":          "{done} / {total} files",
    },
}


def _fmt_eta(secs: float) -> str:
    secs = max(0, int(secs))
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.lang = "zh"

        self.root.geometry("760x720")
        self.root.minsize(660, 620)
        self.root.resizable(True, True)

        # ── State ──────────────────────────────────────────────────────────
        self.process: subprocess.Popen | None = None
        self.log_q: queue.Queue = queue.Queue()
        self.running    = False
        self.batch_total = 0

        # ── GPU status cache (set by _check_gpu_status) ────────────────────
        self._gpu_status_args: tuple | None = None

        # ── Tk variables ───────────────────────────────────────────────────
        self.mode_var      = tk.StringVar(value="single")
        self.input_var     = tk.StringVar()
        self.output_var    = tk.StringVar()
        self.target_var    = tk.StringVar(value="1080p")
        self.method_var    = tk.StringVar(value="simple")
        self.model_var     = tk.StringVar(value="RealESRGAN_x4plus")
        self.recursive_var = tk.BooleanVar(value=False)

        self._build()
        self._apply_lang()
        self._poll()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        threading.Thread(target=self._check_gpu_status, daemon=True).start()

    # ── Translation helper ─────────────────────────────────────────────────

    def _t(self, key: str, **kw) -> str:
        text = LANGS[self.lang].get(key, LANGS["zh"].get(key, key))
        return text.format(**kw) if kw else text

    # ── UI construction ────────────────────────────────────────────────────

    def _build(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")

        px = 14

        # ── Header ────────────────────────────────────────────────────────
        hdr = ttk.Frame(self.root)
        hdr.pack(fill="x", padx=px, pady=(12, 4))
        self._title_lbl = ttk.Label(hdr, font=("Microsoft JhengHei UI", 15, "bold"))
        self._title_lbl.pack(side="left")
        self._lang_btn = ttk.Button(hdr, width=8, command=self._toggle_lang)
        self._lang_btn.pack(side="right")

        # ── Mode ──────────────────────────────────────────────────────────
        self._mode_frame = ttk.LabelFrame(self.root, padding=8)
        self._mode_frame.pack(fill="x", padx=px, pady=4)
        self._rb_single = ttk.Radiobutton(
            self._mode_frame, variable=self.mode_var,
            value="single", command=self._on_mode)
        self._rb_single.pack(side="left", padx=10)
        self._rb_batch = ttk.Radiobutton(
            self._mode_frame, variable=self.mode_var,
            value="batch", command=self._on_mode)
        self._rb_batch.pack(side="left", padx=10)

        # ── Paths ─────────────────────────────────────────────────────────
        self._path_frame = ttk.LabelFrame(self.root, padding=8)
        self._path_frame.pack(fill="x", padx=px, pady=4)
        self._path_frame.columnconfigure(1, weight=1)

        self.input_lbl = ttk.Label(self._path_frame)
        self.input_lbl.grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(self._path_frame, textvariable=self.input_var).grid(
            row=0, column=1, sticky="ew", padx=6)
        self._browse_in_btn = ttk.Button(
            self._path_frame, width=8, command=self._browse_input)
        self._browse_in_btn.grid(row=0, column=2)

        self._output_lbl = ttk.Label(self._path_frame)
        self._output_lbl.grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(self._path_frame, textvariable=self.output_var).grid(
            row=1, column=1, sticky="ew", padx=6)
        self._browse_out_btn = ttk.Button(
            self._path_frame, width=8, command=self._browse_output)
        self._browse_out_btn.grid(row=1, column=2)

        self._recursive_cb = ttk.Checkbutton(
            self._path_frame, variable=self.recursive_var)

        # ── Settings ──────────────────────────────────────────────────────
        self._settings_frame = ttk.LabelFrame(self.root, padding=8)
        self._settings_frame.pack(fill="x", padx=px, pady=4)

        self._target_lbl = ttk.Label(self._settings_frame)
        self._target_lbl.grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(self._settings_frame, textvariable=self.target_var,
                     values=TARGET_OPTS, state="readonly", width=10).grid(
            row=0, column=1, sticky="w", padx=4)

        self._method_lbl = ttk.Label(self._settings_frame)
        self._method_lbl.grid(row=0, column=2, sticky="w", padx=(20, 4))
        self._rb_simple = ttk.Radiobutton(
            self._settings_frame, variable=self.method_var,
            value="simple", command=self._on_method)
        self._rb_simple.grid(row=0, column=3, padx=4)
        self._rb_ai = ttk.Radiobutton(
            self._settings_frame, variable=self.method_var,
            value="ai", command=self._on_method)
        self._rb_ai.grid(row=0, column=4, padx=4)

        self.model_lbl = ttk.Label(self._settings_frame, foreground="gray")
        self.model_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=3)
        self.model_cb = ttk.Combobox(
            self._settings_frame, textvariable=self.model_var,
            values=MODEL_OPTS, state="disabled", width=24)
        self.model_cb.grid(row=1, column=1, columnspan=2, sticky="w", padx=4)

        # ── Buttons ───────────────────────────────────────────────────────
        bf = ttk.Frame(self.root)
        bf.pack(fill="x", padx=px, pady=(6, 2))

        self.start_btn = ttk.Button(bf, command=self._start, width=14)
        self.start_btn.pack(side="left", padx=(0, 4))
        self.stop_btn = ttk.Button(bf, command=self._stop, width=10, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        ttk.Separator(bf, orient="vertical").pack(side="left", fill="y", padx=12, pady=2)
        self._install_btn = ttk.Button(bf, command=self._install_ai, width=16)
        self._install_btn.pack(side="left", padx=4)
        self._clear_btn = ttk.Button(bf, command=self._clear_log, width=10)
        self._clear_btn.pack(side="right")

        # ── GPU status bar ────────────────────────────────────────────────
        self._gpu_bar = ttk.Frame(self.root, relief="flat")
        self._gpu_bar.pack(fill="x", padx=px, pady=(0, 2))
        self.gpu_status_lbl = ttk.Label(
            self._gpu_bar, foreground="gray",
            font=("Microsoft JhengHei UI", 9), anchor="w")
        self.gpu_status_lbl.pack(side="left")
        self.gpu_fix_btn = ttk.Button(
            self._gpu_bar, command=self._install_ai, width=22)

        # ── Progress panel ────────────────────────────────────────────────
        self._progress_frame = ttk.LabelFrame(self.root, padding=(10, 6))
        self._progress_frame.pack(fill="x", padx=px, pady=(4, 2))
        self._progress_frame.columnconfigure(1, weight=1)

        self._overall_lbl = ttk.Label(self._progress_frame, width=8, anchor="w")
        self._overall_lbl.grid(row=0, column=0, sticky="w")
        self.overall_pbar = ttk.Progressbar(
            self._progress_frame, mode="determinate", maximum=100)
        self.overall_pbar.grid(row=0, column=1, sticky="ew", padx=(4, 6))
        self.overall_pct_lbl = ttk.Label(
            self._progress_frame, text="", width=5, anchor="e",
            font=("Consolas", 9))
        self.overall_pct_lbl.grid(row=0, column=2, sticky="e")
        self.overall_info_lbl = ttk.Label(
            self._progress_frame, text="—", foreground="gray",
            font=("Microsoft JhengHei UI", 9))
        self.overall_info_lbl.grid(row=0, column=3, sticky="w", padx=(8, 0))

        self.file_name_lbl = ttk.Label(
            self._progress_frame, text="—", foreground="gray",
            font=("Microsoft JhengHei UI", 9), anchor="w")
        self.file_name_lbl.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 1))

        self._current_lbl = ttk.Label(self._progress_frame, width=8, anchor="w")
        self._current_lbl.grid(row=2, column=0, sticky="w")
        self.file_pbar = ttk.Progressbar(
            self._progress_frame, mode="determinate", maximum=100)
        self.file_pbar.grid(row=2, column=1, sticky="ew", padx=(4, 6))
        self.file_pct_lbl = ttk.Label(
            self._progress_frame, text="", width=5, anchor="e",
            font=("Consolas", 9))
        self.file_pct_lbl.grid(row=2, column=2, sticky="e")

        self.stats_lbl = ttk.Label(
            self._progress_frame, text="", foreground="#555",
            font=("Consolas", 8), anchor="w")
        self.stats_lbl.grid(row=3, column=0, columnspan=4, sticky="w", pady=(3, 0))

        # ── Log ───────────────────────────────────────────────────────────
        self._log_frame = ttk.LabelFrame(self.root, padding=6)
        self._log_frame.pack(fill="both", expand=True, padx=px, pady=(2, 14))

        self.log = scrolledtext.ScrolledText(
            self._log_frame, height=8, state="disabled",
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white", relief="flat")
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok",    foreground="#4ec9b0")
        self.log.tag_config("warn",  foreground="#dcdcaa")
        self.log.tag_config("error", foreground="#f44747")
        self.log.tag_config("info",  foreground="#9cdcfe")
        self.log.tag_config("plain", foreground="#d4d4d4")

    def _apply_lang(self):
        """Update every widget text and the window title to the current language."""
        t = self._t
        self.root.title(t("title"))
        self._title_lbl.config(text=t("header"))
        self._lang_btn.config(text=t("lang_btn"))

        self._mode_frame.config(text=t("mode_frame"))
        self._rb_single.config(text=t("mode_single"))
        self._rb_batch.config(text=t("mode_batch"))

        self._path_frame.config(text=t("path_frame"))
        self.input_lbl.config(
            text=t("input_folder") if self.mode_var.get() == "batch" else t("input_video"))
        self._output_lbl.config(text=t("output_path"))
        self._browse_in_btn.config(text=t("browse"))
        self._browse_out_btn.config(text=t("browse"))
        self._recursive_cb.config(text=t("include_sub"))

        self._settings_frame.config(text=t("settings_frame"))
        self._target_lbl.config(text=t("target_res"))
        self._method_lbl.config(text=t("method"))
        self._rb_simple.config(text=t("method_simple"))
        self._rb_ai.config(text=t("method_ai"))
        self.model_lbl.config(text=t("ai_model"))

        self.start_btn.config(text=t("btn_start"))
        self.stop_btn.config(text=t("btn_stop"))
        self._install_btn.config(text=t("btn_install"))
        self._clear_btn.config(text=t("btn_clear"))
        self.gpu_fix_btn.config(text=t("btn_gpu_fix"))

        self.gpu_status_lbl.config(text=f"  {t('gpu_detecting')}")

        self._progress_frame.config(text=t("progress_frame"))
        self._overall_lbl.config(text=t("overall"))
        self._current_lbl.config(text=t("current"))
        self._log_frame.config(text=t("log_frame"))

        # Re-render GPU status with new language if we already have the result
        if self._gpu_status_args is not None:
            self._render_gpu_status(*self._gpu_status_args)

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self._apply_lang()

    # ── Event handlers ─────────────────────────────────────────────────────

    def _on_mode(self):
        if self.mode_var.get() == "batch":
            self.input_lbl.config(text=self._t("input_folder"))
            self._recursive_cb.grid(row=2, column=0, columnspan=3, sticky="w", pady=3)
        else:
            self.input_lbl.config(text=self._t("input_video"))
            self._recursive_cb.grid_forget()
        self.input_var.set("")
        self.output_var.set("")

    def _on_method(self):
        is_ai = self.method_var.get() == "ai"
        self.model_cb.config(state="readonly" if is_ai else "disabled")
        self.model_lbl.config(foreground="black" if is_ai else "gray")

    def _browse_input(self):
        if self.mode_var.get() == "batch":
            p = filedialog.askdirectory(title=self._t("dlg_browse_in_folder"))
        else:
            p = filedialog.askopenfilename(
                title=self._t("dlg_browse_in_video"),
                filetypes=[
                    (self._t("dlg_video_files"),
                     "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                    (self._t("dlg_all_files"), "*.*"),
                ],
            )
        if p:
            self.input_var.set(p)

    def _browse_output(self):
        if self.mode_var.get() == "batch":
            p = filedialog.askdirectory(title=self._t("dlg_browse_out_folder"))
        else:
            p = filedialog.asksaveasfilename(
                title=self._t("dlg_browse_out_video"),
                defaultextension=".mp4",
                filetypes=[
                    (self._t("dlg_mp4_files"), "*.mp4"),
                    (self._t("dlg_all_files"), "*.*"),
                ],
            )
        if p:
            self.output_var.set(p)

    # ── Core actions ───────────────────────────────────────────────────────

    def _start(self):
        src = self.input_var.get().strip()
        if not src:
            need_key = "dlg_need_folder" if self.mode_var.get() == "batch" else "dlg_need_video"
            messagebox.showerror(self._t("dlg_error"), self._t(need_key))
            return
        if not Path(src).exists():
            messagebox.showerror(self._t("dlg_error"),
                                 self._t("dlg_path_missing", path=src))
            return
        if not UPSCALE_PY.exists():
            messagebox.showerror(self._t("dlg_error"), self._t("dlg_script_missing"))
            return

        self._set_busy(self._t("state_processing"))
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            if self.mode_var.get() == "batch":
                self._run_batch()
            else:
                self.log_q.put(("_file_start", Path(self.input_var.get()).name))
                self._run_single(self.input_var.get(), self.output_var.get() or None)
            self.log_q.put(("_done_ok", None))
        except subprocess.CalledProcessError as e:
            self.log_q.put(("error", self._t("log_proc_error", rc=e.returncode)))
            self.log_q.put(("_done_err", None))
        except Exception as e:
            self.log_q.put(("error", self._t("log_unexpected", err=e)))
            self.log_q.put(("_done_err", None))

    def _run_single(self, src: str, dst: str | None):
        cmd = [PYTHON, str(UPSCALE_PY), src]
        if dst:
            cmd.append(dst)
        cmd += ["--target", self.target_var.get(), "--mode", self.method_var.get()]
        if self.method_var.get() == "ai":
            cmd += ["--model", self.model_var.get()]
        self._exec(cmd)

    def _run_batch(self):
        input_dir  = Path(self.input_var.get())
        output_dir = Path(self.output_var.get()) if self.output_var.get() else input_dir / "upscaled"
        output_dir.mkdir(parents=True, exist_ok=True)

        pattern = "**/*" if self.recursive_var.get() else "*"
        files = sorted(f for f in input_dir.glob(pattern) if f.suffix.lower() in VIDEO_EXTS)

        if not files:
            self.log_q.put(("warn", self._t("log_no_videos")))
            return

        total = len(files)
        self.batch_total = total
        self.log_q.put(("info", self._t("log_found", n=total, path=output_dir)))
        self.log_q.put(("_overall", (0, total)))

        ok = fail = 0
        for i, f in enumerate(files, 1):
            if not self.running:
                break
            out = output_dir / (f.stem + "_upscaled" + f.suffix)
            self.log_q.put(("info", f"\n[{i}/{total}]  {f.name}"))
            self.log_q.put(("_overall", (i - 1, total)))
            self.log_q.put(("_file_start", f.name))
            try:
                self._run_single(str(f), str(out))
                ok += 1
                self.log_q.put(("ok", self._t("log_done", name=out.name)))
            except Exception as e:
                fail += 1
                self.log_q.put(("error", self._t("log_failed", err=e)))

        self.log_q.put(("_overall", (total, total)))
        self.log_q.put(("ok", self._t("log_batch_done", ok=ok, fail=fail)))

    def _exec(self, cmd: list):
        self.log_q.put(("info", "$ " + " ".join(str(c) for c in cmd)))
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=flags,
        )
        for raw in self.process.stdout:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("PROGRESS:"):
                parts = line.split(":")
                if len(parts) == 5:
                    try:
                        pct   = float(parts[1])
                        fps   = parts[2]
                        speed = parts[3]
                        eta   = float(parts[4])
                        self.log_q.put(("_progress", (pct, fps, speed, eta)))
                    except ValueError:
                        pass
                continue
            lo = line.lower()
            if any(k in lo for k in ("error", "錯誤", "failed")):
                tag = "error"
            elif any(k in lo for k in ("warn", "警告")):
                tag = "warn"
            elif any(k in lo for k in ("done", "完成", "✓")):
                tag = "ok"
            else:
                tag = "plain"
            self.log_q.put((tag, line))

        self.process.wait()
        rc = self.process.returncode
        if rc not in (0, None) and self.running:
            raise subprocess.CalledProcessError(rc, cmd)

    def _stop(self):
        self.running = False
        self._kill_children()
        self.log_q.put(("warn", self._t("log_stopped")))
        self.log_q.put(("_done_err", None))

    def _kill_children(self):
        if self.process is None:
            return
        try:
            import psutil
            parent = psutil.Process(self.process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except ImportError:
            self.process.terminate()
        except Exception:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.process = None

    def _on_close(self):
        self.running = False
        self._kill_children()
        self.root.destroy()

    # ── GPU detection ──────────────────────────────────────────────────────

    def _check_gpu_status(self):
        from pathlib import Path as _P
        import shutil as _sh

        nvsmi_paths = [
            _sh.which("nvidia-smi"),
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        ]
        has_nvidia = any(p and _P(p).exists() for p in nvsmi_paths)

        cuda_ok      = False
        gpu_name     = ""
        py_ver       = ""
        is_cpu_build = False
        try:
            import torch
            py_ver       = torch.__version__
            is_cpu_build = "+cpu" in py_ver
            cuda_ok      = torch.cuda.is_available()
            if cuda_ok:
                gpu_name = torch.cuda.get_device_name(0)
        except ImportError:
            py_ver = self._t("gpu_not_installed")

        # Cache the raw args so _apply_lang can re-render with new language
        self._gpu_status_args = (cuda_ok, has_nvidia, is_cpu_build, gpu_name, py_ver)
        self.root.after(0, lambda: self._render_gpu_status(
            cuda_ok, has_nvidia, is_cpu_build, gpu_name, py_ver))

    def _render_gpu_status(self, cuda_ok, has_nvidia, is_cpu_build, gpu_name, py_ver):
        if cuda_ok:
            text     = self._t("gpu_ready", name=gpu_name, ver=py_ver)
            color    = "#107c10"
            show_fix = False
        elif has_nvidia and is_cpu_build:
            text     = self._t("gpu_cpu_build", ver=py_ver)
            color    = "#c42b1c"
            show_fix = True
        elif has_nvidia and not cuda_ok:
            text     = self._t("gpu_cuda_fail", ver=py_ver)
            color    = "#c42b1c"
            show_fix = True
        elif not has_nvidia:
            text     = self._t("gpu_no_nvidia", ver=py_ver)
            color    = "#797775"
            show_fix = False
        else:
            text     = self._t("gpu_unknown", ver=py_ver)
            color    = "#797775"
            show_fix = False

        self.gpu_status_lbl.config(text=f"  {text}", foreground=color)
        if show_fix:
            self.gpu_fix_btn.pack(side="left", padx=(8, 0))
        else:
            self.gpu_fix_btn.pack_forget()

    # ── Install ────────────────────────────────────────────────────────────

    def _install_ai(self):
        if self.running:
            messagebox.showwarning(self._t("dlg_warn"), self._t("dlg_need_video"))
            return
        if not messagebox.askyesno(self._t("dlg_install_title"),
                                   self._t("dlg_install_body")):
            return

        self._set_busy(self._t("state_installing"))

        def _do():
            import shutil
            from pathlib import Path as _P
            _nvsmi = [
                shutil.which("nvidia-smi"),
                r"C:\Windows\System32\nvidia-smi.exe",
                r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
            ]
            has_nvidia = any(p and _P(p).exists() for p in _nvsmi)

            if has_nvidia:
                torch_cmd = [PYTHON, "-m", "pip", "install", "torch", "torchvision",
                             "--index-url", "https://download.pytorch.org/whl/cu128"]
                self.log_q.put(("ok", self._t("log_installing_cuda")))
            else:
                torch_cmd = [PYTHON, "-m", "pip", "install", "torch", "torchvision",
                             "--index-url", "https://download.pytorch.org/whl/cpu"]
                self.log_q.put(("warn", self._t("log_installing_cpu")))

            steps = [
                torch_cmd,
                [PYTHON, "-m", "pip", "install", "realesrgan", "basicsr"],
                [PYTHON, "-m", "pip", "install", "opencv-python"],
            ]
            try:
                for cmd in steps:
                    self._exec(cmd)
                self.log_q.put(("ok", self._t("log_install_done")))
                self.log_q.put(("_done_ok", None))
                threading.Thread(target=self._check_gpu_status, daemon=True).start()
            except Exception as e:
                self.log_q.put(("error", self._t("log_install_fail", err=e)))
                self.log_q.put(("_done_err", None))

        threading.Thread(target=_do, daemon=True).start()

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    # ── State helpers ──────────────────────────────────────────────────────

    def _set_busy(self, msg: str):
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.overall_pbar["value"] = 0
        self.file_pbar["value"] = 0
        self.overall_pct_lbl.config(text="")
        self.file_pct_lbl.config(text="")
        self.overall_info_lbl.config(text=msg, foreground="#0078d4")
        self.file_name_lbl.config(text=self._t("ready"), foreground="gray")
        self.stats_lbl.config(text="")

    def _set_idle(self, ok: bool):
        self.running = False
        self.process = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if ok:
            self.overall_pbar["value"] = 100
            self.file_pbar["value"] = 100
            self.overall_pct_lbl.config(text="100%")
            self.file_pct_lbl.config(text="100%")
            self.overall_info_lbl.config(text=self._t("state_done"),
                                         foreground="#107c10")
        else:
            self.overall_info_lbl.config(text=self._t("state_stopped"),
                                         foreground="#c42b1c")
        self.stats_lbl.config(text="")

    def _append(self, text: str, tag: str = "plain"):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")

    # ── Queue polling ──────────────────────────────────────────────────────

    def _poll(self):
        try:
            while True:
                tag, payload = self.log_q.get_nowait()

                if tag == "_done_ok":
                    self._set_idle(ok=True)

                elif tag == "_done_err":
                    self._set_idle(ok=False)

                elif tag == "_file_start":
                    self.file_name_lbl.config(text=f"  {payload}", foreground="#cccccc")
                    self.file_pbar["value"] = 0
                    self.file_pct_lbl.config(text="0%")
                    self.stats_lbl.config(text="")

                elif tag == "_overall":
                    done, total = payload
                    pct = done / total * 100 if total else 0
                    self.overall_pbar["value"] = pct
                    self.overall_pct_lbl.config(text=f"{pct:.0f}%")
                    self.overall_info_lbl.config(
                        text=self._t("state_files", done=done, total=total),
                        foreground="#0078d4")

                elif tag == "_progress":
                    pct, fps, speed, eta = payload
                    self.file_pbar["value"] = pct
                    self.file_pct_lbl.config(text=f"{pct:.0f}%")
                    if speed == "AI":
                        stats = (f"  {fps} {self._t('fps_unit')}   "
                                 f"{self._t('ai_processing')}   "
                                 f"{self._t('remaining')} {_fmt_eta(eta)}")
                    else:
                        stats = (f"  {fps} fps   "
                                 f"{self._t('speed_x')}{speed}   "
                                 f"{self._t('remaining')} {_fmt_eta(eta)}")
                    self.stats_lbl.config(text=stats)

                else:
                    self._append(payload, tag)

        except queue.Empty:
            pass
        self.root.after(80, self._poll)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
