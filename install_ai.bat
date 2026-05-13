@echo off
echo ============================================
echo  Installing AI upscaling dependencies...
echo ============================================
echo.

echo [1/3] Installing PyTorch (CPU version - safe for all machines)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

echo.
echo [2/3] Installing Real-ESRGAN and BasicSR
pip install realesrgan basicsr

echo.
echo [3/3] Installing OpenCV
pip install opencv-python

echo.
echo ============================================
echo  Done! You can now run:
echo  python upscale.py your_video.mp4 --mode ai
echo ============================================
pause
