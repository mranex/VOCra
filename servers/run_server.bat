@echo off
cd /d "C:\Nghich\vocra\tools"
call C:\Nghich\vocra\tools\llama-server.exe ^
  -m ^
  C:\Nghich\vocra\models\paddleocr_vl\model.gguf ^
  --mmproj ^
  C:\Nghich\vocra\models\paddleocr_vl\mmproj.gguf ^
  --host ^
  127.0.0.1 ^
  --port ^
  8080 ^
  -c ^
  8192 ^
  --parallel ^
  3 ^
  -ngl ^
  99 ^
  --temp ^
  0 ^
  --no-cache-prompt ^
  --cache-ram ^
  0 ^
  --no-cache-idle-slots
echo.
echo Server stopped. Press any key to close this window.
pause >nul
