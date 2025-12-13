@echo off
setlocal

rem --- Determine output directory relative to this batch file ---
set "BASEDIR=%~dp0"
set "OUTDIR=%BASEDIR%inputs"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

rem --- Copy vocab.db from Kindle via Shell.Application COM with desired filename ---
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
  "$tempPath = [System.IO.Path]::GetTempFileName();" ^
  "$s.NameSpace([System.IO.Path]::GetDirectoryName($tempPath)).CopyHere($db,16);" ^
  "$tempVocab = Join-Path ([System.IO.Path]::GetDirectoryName($tempPath)) 'vocab.db';" ^
  "Move-Item $tempVocab '%OUTDIR%\vocab_powershell_copy.db' -Force;" ^
  "Remove-Item $tempPath -Force -ErrorAction SilentlyContinue"

set PSRC=%errorlevel%
exit /b %PSRC%

endlocal
