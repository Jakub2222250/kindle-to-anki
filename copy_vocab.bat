@echo off
setlocal

rem --- Determine output directory relative to this batch file ---
set "BASEDIR=%~dp0"
set "OUTDIR=%BASEDIR%inputs"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

rem --- Generate timestamp YYYYMMDD_HHMMSS safely ---
for /f "tokens=1-3 delims=/- " %%a in ("%date%") do (
    set "MM=%%a"
    set "DD=%%b"
    set "YYYY=%%c"
)
for /f "tokens=1-3 delims=:." %%a in ("%time%") do (
    set "HH=%%a"
    set "MIN=%%b"
    set "SEC=%%c"
)
set "TIMESTAMP=%YYYY%%MM%%DD%_%HH%%MIN%%SEC%"

rem --- If vocab.db exists, rename it with timestamp ---
if exist "%OUTDIR%\vocab.db" (
    ren "%OUTDIR%\vocab.db" "vocab_%TIMESTAMP%.db"
)

rem --- Copy vocab.db from Kindle via Shell.Application COM ---
powershell -nop -c ^
  "$s = New-Object -ComObject Shell.Application;" ^
  "$drives = $s.Namespace(17).Items();" ^
  "$mtp = $drives | Where-Object { $_.IsFolder -and $_.Name -eq 'Kindle Paperwhite Signature Edition' } | Select-Object -First 1;" ^
  "if (-not $mtp) { Write-Error 'Kindle not found'; exit 1 };" ^
  "$root = $mtp.GetFolder;" ^
  "$internal = $root.Items() | Where-Object { $_.Name -eq 'Internal Storage' } | Select-Object -First 1;" ^
  "$system = $internal.GetFolder.Items() | Where-Object { $_.Name -eq 'system' } | Select-Object -First 1;" ^
  "$voc = $system.GetFolder.Items() | Where-Object { $_.Name -eq 'vocabulary' } | Select-Object -First 1;" ^
  "$db = $voc.GetFolder.ParseName('vocab.db');" ^
  "if (-not $db) { Write-Error 'vocab.db not found'; exit 1 };" ^
  "$OUT = '%OUTDIR%' ;" ^
  "$s.NameSpace($OUT).CopyHere($db,16)"

echo Done.
endlocal
