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


def _fmt_eta(secs: float) -> str:
    secs = max(0, int(secs))
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("影片超解析度放大工具")
        self.root.geometry("760x720")
        self.root.minsize(660, 620)
        self.root.resizable(True, True)

        # ── State ──────────────────────────────────────────────────────────
        self.process: subprocess.Popen | None = None
        self.log_q: queue.Queue = queue.Queue()
        self.running   = False
        self.batch_total = 0

        # ── Tk variables ───────────────────────────────────────────────────
        self.mode_var      = tk.StringVar(value="single")
        self.input_var     = tk.StringVar()
        self.output_var    = tk.StringVar()
        self.target_var    = tk.StringVar(value="1080p")
        self.method_var    = tk.StringVar(value="simple")
        self.model_var     = tk.StringVar(value="RealESRGAN_x4plus")
        self.recursive_var = tk.BooleanVar(value=False)

        self._build()
        self._poll()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ────────────────────────────────────────────────────

    def _build(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")

        px = 14

        # Title
        hdr = ttk.Frame(self.root)
        hdr.pack(fill="x", padx=px, pady=(12, 4))
        ttk.Label(hdr, text="影片超解析度放大工具",
                  font=("Microsoft JhengHei UI", 15, "bold")).pack(side="left")

        # ── Mode ──────────────────────────────────────────────────────────
        mf = ttk.LabelFrame(self.root, text="處理模式", padding=8)
        mf.pack(fill="x", padx=px, pady=4)
        ttk.Radiobutton(mf, text="單一影片", variable=self.mode_var,
                        value="single", command=self._on_mode).pack(side="left", padx=10)
        ttk.Radiobutton(mf, text="批次轉檔（整個資料夾）", variable=self.mode_var,
                        value="batch",  command=self._on_mode).pack(side="left", padx=10)

        # ── Paths ─────────────────────────────────────────────────────────
        pf = ttk.LabelFrame(self.root, text="路徑設定", padding=8)
        pf.pack(fill="x", padx=px, pady=4)
        pf.columnconfigure(1, weight=1)

        self.input_lbl = ttk.Label(pf, text="輸入影片：")
        self.input_lbl.grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(pf, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(pf, text="瀏覽", command=self._browse_input, width=8).grid(row=0, column=2)

        ttk.Label(pf, text="輸出位置：").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(pf, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(pf, text="瀏覽", command=self._browse_output, width=8).grid(row=1, column=2)

        self.recursive_cb = ttk.Checkbutton(pf, text="包含子資料夾", variable=self.recursive_var)

        # ── Settings ──────────────────────────────────────────────────────
        sf = ttk.LabelFrame(self.root, text="轉換設定", padding=8)
        sf.pack(fill="x", padx=px, pady=4)

        ttk.Label(sf, text="目標解析度：").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(sf, textvariable=self.target_var, values=TARGET_OPTS,
                     state="readonly", width=10).grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(sf, text="處理方式：").grid(row=0, column=2, sticky="w", padx=(20, 4))
        ttk.Radiobutton(sf, text="快速 Lanczos", variable=self.method_var,
                        value="simple", command=self._on_method).grid(row=0, column=3, padx=4)
        ttk.Radiobutton(sf, text="AI 超解析 (Real-ESRGAN)", variable=self.method_var,
                        value="ai",     command=self._on_method).grid(row=0, column=4, padx=4)

        self.model_lbl = ttk.Label(sf, text="AI 模型：", foreground="gray")
        self.model_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=3)
        self.model_cb = ttk.Combobox(sf, textvariable=self.model_var, values=MODEL_OPTS,
                                     state="disabled", width=24)
        self.model_cb.grid(row=1, column=1, columnspan=2, sticky="w", padx=4)

        # ── Buttons ───────────────────────────────────────────────────────
        bf = ttk.Frame(self.root)
        bf.pack(fill="x", padx=px, pady=(6, 2))

        self.start_btn = ttk.Button(bf, text="▶  開始轉換", command=self._start, width=14)
        self.start_btn.pack(side="left", padx=(0, 4))
        self.stop_btn = ttk.Button(bf, text="■  停止", command=self._stop, width=10, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        ttk.Separator(bf, orient="vertical").pack(side="left", fill="y", padx=12, pady=2)
        ttk.Button(bf, text="安裝 AI 套件", command=self._install_ai, width=14).pack(side="left", padx=4)
        ttk.Button(bf, text="清除日誌",      command=self._clear_log,  width=10).pack(side="right")

        # ── Progress panel ────────────────────────────────────────────────
        prog = ttk.LabelFrame(self.root, text="轉換進度", padding=(10, 6))
        prog.pack(fill="x", padx=px, pady=(4, 2))
        prog.columnconfigure(1, weight=1)

        # Overall row (batch)
        ttk.Label(prog, text="整體：", width=6, anchor="w").grid(row=0, column=0, sticky="w")
        self.overall_pbar = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.overall_pbar.grid(row=0, column=1, sticky="ew", padx=(4, 6))
        self.overall_pct_lbl = ttk.Label(prog, text="", width=5, anchor="e",
                                         font=("Consolas", 9))
        self.overall_pct_lbl.grid(row=0, column=2, sticky="e")
        self.overall_info_lbl = ttk.Label(prog, text="—", foreground="gray",
                                          font=("Microsoft JhengHei UI", 9))
        self.overall_info_lbl.grid(row=0, column=3, sticky="w", padx=(8, 0))

        # Current file name
        self.file_name_lbl = ttk.Label(prog, text="—", foreground="gray",
                                       font=("Microsoft JhengHei UI", 9), anchor="w")
        self.file_name_lbl.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 1))

        # File progress row
        ttk.Label(prog, text="目前：", width=6, anchor="w").grid(row=2, column=0, sticky="w")
        self.file_pbar = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.file_pbar.grid(row=2, column=1, sticky="ew", padx=(4, 6))
        self.file_pct_lbl = ttk.Label(prog, text="", width=5, anchor="e",
                                      font=("Consolas", 9))
        self.file_pct_lbl.grid(row=2, column=2, sticky="e")

        # Stats row: fps / speed / elapsed / ETA
        self.stats_lbl = ttk.Label(prog, text="", foreground="#555",
                                   font=("Consolas", 8), anchor="w")
        self.stats_lbl.grid(row=3, column=0, columnspan=4, sticky="w", pady=(3, 0))

        # ── Log ───────────────────────────────────────────────────────────
        lf = ttk.LabelFrame(self.root, text="執行日誌", padding=6)
        lf.pack(fill="both", expand=True, padx=px, pady=(2, 14))

        self.log = scrolledtext.ScrolledText(
            lf, height=8, state="disabled",
            font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white", relief="flat"
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok",    foreground="#4ec9b0")
        self.log.tag_config("warn",  foreground="#dcdcaa")
        self.log.tag_config("error", foreground="#f44747")
        self.log.tag_config("info",  foreground="#9cdcfe")
        self.log.tag_config("plain", foreground="#d4d4d4")

    # ── Event handlers ─────────────────────────────────────────────────────

    def _on_mode(self):
        if self.mode_var.get() == "batch":
            self.input_lbl.config(text="輸入資料夾：")
            self.recursive_cb.grid(row=2, column=0, columnspan=3, sticky="w", pady=3)
        else:
            self.input_lbl.config(text="輸入影片：")
            self.recursive_cb.grid_forget()
        self.input_var.set("")
        self.output_var.set("")

    def _on_method(self):
        is_ai = self.method_var.get() == "ai"
        self.model_cb.config(state="readonly" if is_ai else "disabled")
        self.model_lbl.config(foreground="black" if is_ai else "gray")

    def _browse_input(self):
        if self.mode_var.get() == "batch":
            p = filedialog.askdirectory(title="選擇輸入資料夾")
        else:
            p = filedialog.askopenfilename(
                title="選擇影片檔案",
                filetypes=[("影片檔案", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v"),
                           ("所有檔案", "*.*")]
            )
        if p:
            self.input_var.set(p)

    def _browse_output(self):
        if self.mode_var.get() == "batch":
            p = filedialog.askdirectory(title="選擇輸出資料夾")
        else:
            p = filedialog.asksaveasfilename(
                title="另存輸出影片",
                defaultextension=".mp4",
                filetypes=[("MP4 影片", "*.mp4"), ("所有檔案", "*.*")]
            )
        if p:
            self.output_var.set(p)

    # ── Core actions ───────────────────────────────────────────────────────

    def _start(self):
        src = self.input_var.get().strip()
        if not src:
            messagebox.showerror("錯誤", "請先選擇" + ("資料夾" if self.mode_var.get() == "batch" else "影片檔案"))
            return
        if not Path(src).exists():
            messagebox.showerror("錯誤", f"路徑不存在：{src}")
            return
        if not UPSCALE_PY.exists():
            messagebox.showerror("錯誤", "找不到 upscale.py，請確認與 launcher.py 在同一資料夾")
            return

        self._set_busy("處理中...")
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
            self.log_q.put(("error", f"程式錯誤（returncode={e.returncode}）"))
            self.log_q.put(("_done_err", None))
        except Exception as e:
            self.log_q.put(("error", f"未預期錯誤：{e}"))
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
            self.log_q.put(("warn", "資料夾內找不到影片檔案"))
            return

        total = len(files)
        self.batch_total = total
        self.log_q.put(("info", f"找到 {total} 個影片，輸出至：{output_dir}"))
        self.log_q.put(("_overall", (0, total)))

        ok = fail = 0
        for i, f in enumerate(files, 1):
            if not self.running:
                break

            out = output_dir / (f.stem + "_upscaled" + f.suffix)
            self.log_q.put(("info", f"\n[{i}/{total}]  {f.name}"))
            self.log_q.put(("_overall", (i - 1, total)))   # progress before this file starts
            self.log_q.put(("_file_start", f.name))

            try:
                self._run_single(str(f), str(out))
                ok += 1
                self.log_q.put(("ok", f"  完成：{out.name}"))
            except Exception as e:
                fail += 1
                self.log_q.put(("error", f"  失敗：{e}"))

        # Overall bar at 100% after all files
        self.log_q.put(("_overall", (total, total)))
        self.log_q.put(("ok", f"\n批次完成 — 成功 {ok} 個，失敗 {fail} 個"))

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

            # Structured progress from upscale.py — update bars, don't log
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
        self.log_q.put(("warn", "已由使用者停止"))
        self.log_q.put(("_done_err", None))

    def _kill_children(self):
        """Kill the upscale.py subprocess and any FFmpeg processes it spawned."""
        if self.process is None:
            return
        try:
            # Use psutil if available — kills the whole process tree (upscale.py + ffmpeg)
            import psutil
            parent = psutil.Process(self.process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except ImportError:
            # Fallback: terminate the direct child only
            self.process.terminate()
        except Exception:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.process = None

    def _on_close(self):
        """Handle window X button — stop encoding before destroying the window."""
        self.running = False
        self._kill_children()
        self.root.destroy()

    def _install_ai(self):
        if self.running:
            messagebox.showwarning("提示", "請先停止目前的任務")
            return
        if not messagebox.askyesno(
            "安裝 AI 套件",
            "將安裝以下套件（約需 3–10 分鐘）：\n\n"
            "  • torch + torchvision（自動偵測 GPU，有 NVIDIA 裝 CUDA 版）\n"
            "  • realesrgan\n  • basicsr\n  • opencv-python\n\n"
            "是否繼續？"
        ):
            return

        self._set_busy("安裝 AI 套件中...")

        def _do():
            import shutil
            has_nvidia = shutil.which("nvidia-smi") is not None
            if has_nvidia:
                torch_cmd = [PYTHON, "-m", "pip", "install", "torch", "torchvision",
                             "--index-url", "https://download.pytorch.org/whl/cu121"]
                self.log_q.put(("ok", "偵測到 NVIDIA GPU，安裝 CUDA 版 PyTorch（cu121）..."))
            else:
                torch_cmd = [PYTHON, "-m", "pip", "install", "torch", "torchvision",
                             "--index-url", "https://download.pytorch.org/whl/cpu"]
                self.log_q.put(("warn", "未偵測到 NVIDIA GPU，安裝 CPU 版 PyTorch（速度較慢）"))

            steps = [
                torch_cmd,
                [PYTHON, "-m", "pip", "install", "realesrgan", "basicsr"],
                [PYTHON, "-m", "pip", "install", "opencv-python"],
            ]
            try:
                for cmd in steps:
                    self._exec(cmd)
                self.log_q.put(("ok", "\nAI 套件安裝完成！"))
                self.log_q.put(("_done_ok", None))
            except Exception as e:
                self.log_q.put(("error", f"安裝失敗：{e}"))
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
        self.file_name_lbl.config(text="準備中…", foreground="gray")
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
            self.overall_info_lbl.config(text="全部完成", foreground="#107c10")
        else:
            self.overall_info_lbl.config(text="已停止", foreground="#c42b1c")
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
                    # payload = filename string
                    self.file_name_lbl.config(text=f"  {payload}", foreground="#cccccc")
                    self.file_pbar["value"] = 0
                    self.file_pct_lbl.config(text="0%")
                    self.stats_lbl.config(text="")

                elif tag == "_overall":
                    # payload = (done, total)
                    done, total = payload
                    pct = done / total * 100 if total else 0
                    self.overall_pbar["value"] = pct
                    self.overall_pct_lbl.config(text=f"{pct:.0f}%")
                    self.overall_info_lbl.config(
                        text=f"{done} / {total} 個檔案",
                        foreground="#0078d4"
                    )

                elif tag == "_progress":
                    # payload = (pct, fps, speed, eta_secs)
                    pct, fps, speed, eta = payload
                    self.file_pbar["value"] = pct
                    self.file_pct_lbl.config(text=f"{pct:.0f}%")
                    if speed == "AI":
                        stats = f"  {fps} 幀/秒   AI 處理中   剩餘 {_fmt_eta(eta)}"
                    else:
                        stats = f"  {fps} fps   速度 ×{speed}   剩餘 {_fmt_eta(eta)}"
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
