@echo off
REM Builds CTFToyBox.exe on Windows.
REM
REM Usage (from project root):
REM     packaging\build-windows.bat
REM
REM Output: dist\CTFToyBox.exe

setlocal enabledelayedexpansion

REM --- Move to project root regardless of where the script is invoked from
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
pushd "%PROJECT_DIR%"

echo ==^> Project root: %CD%

REM --- 1. Make sure pyinstaller + dependencies are installed
echo ==^> Installing build dependencies...
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt || goto :fail
python -m pip install pyinstaller || goto :fail

REM --- 2. Clean any previous build
echo ==^> Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM --- 3. Build
echo ==^> Running PyInstaller...
pyinstaller packaging\ctftoybox.spec --clean --noconfirm || goto :fail

REM --- 4. Report result
set "EXE=%CD%\dist\CTFToyBox.exe"
if exist "%EXE%" (
    echo.
    echo ==^> SUCCESS.
    echo     %EXE%
    echo.
    echo Distribute by sharing this single .exe file.
    popd
    endlocal
    exit /b 0
)

:fail
echo ==^> Build failed. See output above.
popd
endlocal
exit /b 1