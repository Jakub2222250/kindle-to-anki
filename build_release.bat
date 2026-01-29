@echo off
setlocal

echo Building kindle-to-anki executable...
pyinstaller --onefile --name kindle-to-anki src/kindle_to_anki/ui/app.py

echo Preparing release package...
if exist "dist\kindle-to-anki-package" rmdir /s /q "dist\kindle-to-anki-package"
mkdir "dist\kindle-to-anki-package"
copy "dist\kindle-to-anki.exe" "dist\kindle-to-anki-package\"

mkdir "dist\kindle-to-anki-package\data\config"
mkdir "dist\kindle-to-anki-package\data\inputs"
mkdir "dist\kindle-to-anki-package\data\outputs"
copy "data\config\config.sample.json" "dist\kindle-to-anki-package\data\config\"
copy "data\config\models.yaml" "dist\kindle-to-anki-package\data\config\"

echo Copying prompt files...
for /d %%T in (src\kindle_to_anki\tasks\*) do (
    if exist "%%T\prompts" (
        mkdir "dist\kindle-to-anki-package\tasks\%%~nxT\prompts" 2>nul
        copy "%%T\prompts\*.json" "dist\kindle-to-anki-package\tasks\%%~nxT\prompts\" 2>nul
        copy "%%T\prompts\*.txt" "dist\kindle-to-anki-package\tasks\%%~nxT\prompts\" 2>nul
    )
)

echo Done! Package ready in dist\kindle-to-anki-package
pause
