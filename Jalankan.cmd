@echo off
setlocal
cd /d "%~dp0"
if exist "Mulai-Model-Lokal.ps1" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Mulai-Model-Lokal.ps1"
  if errorlevel 1 goto failed
)
if exist "portable\LinguaPlay\LinguaPlay.exe" (
  start "" "%~dp0portable\LinguaPlay\LinguaPlay.exe"
  exit /b
)
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import PySide6, PIL, winrt.windows.media.ocr, ctranslate2, sentencepiece, psutil" >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe main.py
if errorlevel 1 goto failed
exit /b
:failed
echo Aplikasi belum dapat dijalankan. Baca README.md untuk persyaratan dan pengaturan.
pause
exit /b 1
