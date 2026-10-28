@echo off
setlocal
cd /d "%~dp0"
if exist "Mulai-Model-Lokal.ps1" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Mulai-Model-Lokal.ps1"
  if errorlevel 1 goto failed
)
if exist "portable\LinguaPlay\LinguaPlay.exe" (
  if not exist "main.py" (
    start "" "%~dp0portable\LinguaPlay\LinguaPlay.exe"
    exit /b
  )
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$src = Get-ChildItem '%~dp0' -Recurse -File -Filter '*.py' | Where-Object { $_.FullName -notlike '*\portable\*' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($src -and ((Get-Item '%~dp0portable\LinguaPlay\LinguaPlay.exe').LastWriteTime -ge $src.LastWriteTime)) { exit 0 } else { exit 1 }"
  if not errorlevel 1 (
    start "" "%~dp0portable\LinguaPlay\LinguaPlay.exe"
    exit /b
  )
)
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip --version >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>&1
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
