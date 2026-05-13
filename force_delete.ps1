#Requires -Version 5.0
param([string[]]$FilePaths = @())

$host.UI.RawUI.WindowTitle = "Force Delete Locked Files"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Force Release and Delete Locked Files"     -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Kill locking processes ────────────────────────────────────────
Write-Host "[1/3] Stopping ffmpeg / upscale processes..." -ForegroundColor Yellow

$killed = 0

# Kill by image name
"ffmpeg","ffprobe" | ForEach-Object {
    $procs = Get-Process -Name $_ -ErrorAction SilentlyContinue
    $procs | ForEach-Object {
        Write-Host "      Killing $($_.Name)  (PID $($_.Id))"
        $_ | Stop-Process -Force -ErrorAction SilentlyContinue
        $killed++
    }
}

# Kill python processes running upscale.py
Get-WmiObject Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'upscale\.py' } |
    ForEach-Object {
        Write-Host "      Killing upscale.py  (PID $($_.ProcessId))"
        Stop-Process -Id ([int]$_.ProcessId) -Force -ErrorAction SilentlyContinue
        $killed++
    }

if ($killed -eq 0) {
    Write-Host "      (no matching processes found)" -ForegroundColor Gray
} else {
    Write-Host "      Killed $killed process(es)" -ForegroundColor Green
}

Write-Host "      Waiting 3 s for OS to release file handles..."
Start-Sleep -Seconds 3
Write-Host ""

# ── Step 2: Pick files if none were dragged ────────────────────────────────
if ($FilePaths.Count -eq 0) {
    Write-Host "[2/3] Opening file picker..." -ForegroundColor Yellow
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title       = "Select locked files to force-delete  (Ctrl = multi-select)"
    $dlg.Multiselect = $true
    $dlg.Filter      = "Video files (*.mp4;*.mkv;*.avi;*.mov;*.wmv)|*.mp4;*.mkv;*.avi;*.mov;*.wmv|All files (*.*)|*.*"
    $dlg.InitialDirectory = $PSScriptRoot

    if ($dlg.ShowDialog() -ne "OK" -or $dlg.FileNames.Count -eq 0) {
        Write-Host "      No files selected." -ForegroundColor Gray
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 0
    }
    $FilePaths = $dlg.FileNames
} else {
    Write-Host "[2/3] Files passed as arguments: $($FilePaths.Count)" -ForegroundColor Yellow
}
Write-Host ""

# ── Step 3: Delete (retry x5, then schedule on reboot) ────────────────────
Write-Host "[3/3] Deleting $($FilePaths.Count) file(s)..." -ForegroundColor Yellow
Write-Host ""

# Load MoveFileEx for the reboot-deletion fallback
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class Kernel32 {
    [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
    public static extern bool MoveFileEx(string src, string dst, int flags);
}
'@ -ErrorAction SilentlyContinue

$ok = 0; $reboot = 0; $fail = 0

foreach ($path in $FilePaths) {
    $name = [IO.Path]::GetFileName($path)

    if (!(Test-Path -LiteralPath $path)) {
        Write-Host "  [SKIP]    $name  (file not found)" -ForegroundColor DarkGray
        continue
    }

    # Try up to 5 times, 1 second apart
    $deleted = $false
    for ($i = 1; $i -le 5; $i++) {
        try {
            Remove-Item -LiteralPath $path -Force -ErrorAction Stop
            $deleted = $true
            break
        } catch {
            if ($i -lt 5) {
                Write-Host "  attempt $i failed, retrying..." -ForegroundColor DarkGray
                Start-Sleep -Seconds 1
            }
        }
    }

    if ($deleted) {
        Write-Host "  [OK]      $name" -ForegroundColor Green
        $ok++
        continue
    }

    # Fallback: schedule deletion on next Windows reboot via MoveFileEx
    try {
        $result = [Kernel32]::MoveFileEx($path, $null, 4)   # 4 = MOVEFILE_DELAY_UNTIL_REBOOT
        if ($result) {
            Write-Host "  [REBOOT]  $name" -ForegroundColor Yellow
            Write-Host "            -> will be deleted automatically on next reboot" -ForegroundColor DarkYellow
            $reboot++
        } else {
            $err = [ComponentModel.Win32Exception][Runtime.InteropServices.Marshal]::GetLastWin32Error()
            Write-Host "  [FAIL]    $name" -ForegroundColor Red
            Write-Host "            -> $err" -ForegroundColor DarkRed
            Write-Host "            -> try running force_delete.bat as Administrator" -ForegroundColor DarkRed
            $fail++
        }
    } catch {
        Write-Host "  [FAIL]    $name  ($_)" -ForegroundColor Red
        $fail++
    }
}

# ── Summary ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  OK: $ok   Scheduled(reboot): $reboot   Failed: $fail" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

if ($reboot -gt 0) {
    Write-Host ""
    Write-Host "  Files marked [REBOOT] will be deleted after you restart Windows." -ForegroundColor Yellow
}
if ($fail -gt 0) {
    Write-Host ""
    Write-Host "  Files marked [FAIL]: right-click force_delete.bat" -ForegroundColor Red
    Write-Host "  and choose 'Run as administrator', then try again." -ForegroundColor Red
}

Write-Host ""
Read-Host "Press Enter to exit"
