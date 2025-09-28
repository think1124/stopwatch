@echo off
:: UTF-8 인코딩으로 설정하여 한글 깨짐을 방지합니다.
chcp 65001 > nul
setlocal enabledelayedexpansion

:: ==================================================
:: 설정
:: ==================================================
set PYTHON_SCRIPT=GO.py
set EXE_NAME=GO
set ICON_FILE=icon.ico

:: ==================================================
:: [1/7] 이전 컴파일 기록을 삭제합니다...
:: ==================================================
echo [1/7] 이전 컴파일 기록을 삭제합니다...
if exist "build" (rmdir /s /q build)
if exist "dist" (rmdir /s /q dist)
if exist "*.spec" (del "*.spec")
echo 완료.
echo.

:: ==================================================
:: [2/7] 파이썬 가상환경(venv)을 설정합니다...
:: ==================================================
echo [2/7] 파이썬 가상환경(venv)을 설정합니다...
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
echo 가상환경 활성화 완료.
echo.

:: ==================================================
:: [3/7] 필수 라이브러리를 설치 또는 업데이트합니다...
:: ==================================================
echo [3/7] 필수 라이브러리를 설치 또는 업데이트합니다...
pip install --upgrade pip
pip install pyqt5 opencv-python pynput pygetwindow psutil pywin32 requests pyinstaller certifi
echo 라이브러리 준비 완료.
echo.

:: ==================================================
:: [4/7] SSL 인증서 파일 경로를 찾습니다 (get_cert_path.py 실행)...
:: ==================================================
echo [4/7] SSL 인증서 파일 경로를 찾습니다 (get_cert_path.py 실행)...
for /f "delims=" %%i in ('python get_cert_path.py') do set CERT_PATH=%%i
if not defined CERT_PATH (
    echo [오류] SSL 인증서 경로를 찾는데 실패했습니다.
    goto error
)
echo 경로 확인: !CERT_PATH!
echo.

:: ==================================================
:: [5/7] PyInstaller로 프로그램을 컴파일합니다...
:: ==================================================
echo [5/7] PyInstaller로 프로그램을 컴파일합니다...
echo (이 과정이 가장 오래 걸립니다. 잠시만 기다려주세요.)
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --noupx ^
    --name "!EXE_NAME!" ^
    --icon "!ICON_FILE!" ^
    --add-data "!CERT_PATH!;certifi" ^
    --hidden-import "unicodedata" ^
    !PYTHON_SCRIPT!

if %errorlevel% neq 0 (
    goto error
)
echo 컴파일 완료.
echo.

:: ==================================================
:: [6/7] 불필요한 파일을 정리합니다...
:: ==================================================
echo [6/7] 불필요한 파일을 정리합니다...
if exist "build" (rmdir /s /q build)
if exist "*.spec" (del "*.spec")
echo 정리 완료.
echo.

:: ==================================================
:: [7/7] 작업 완료
:: ==================================================
echo ******************************************************
echo  [성공] 작업이 완료되었습니다!
echo  'dist' 폴더에서 '!EXE_NAME!.exe' 파일을 확인하세요.
echo ******************************************************
echo.
pause
exit /b 0

:error
echo.
echo ******************************************************
echo  [오류] 작업에 실패했습니다!
echo  위의 에러 메시지를 확인해주세요.
echo ******************************************************
echo.
pause
exit /b 1