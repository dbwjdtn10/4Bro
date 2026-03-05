@echo off
chcp 65001 >nul
echo ============================================
echo   4Bro exe 빌드
echo ============================================
echo.

:: Check PyInstaller
pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [..] PyInstaller 설치 중...
    pip install pyinstaller
)

echo [..] 빌드 시작...
pyinstaller build.spec --clean --noconfirm

echo.
if exist dist\4Bro\4Bro.exe (
    echo [OK] 빌드 성공!
    echo     dist\4Bro\4Bro.exe
) else (
    echo [FAIL] 빌드 실패. 위의 오류를 확인해주세요.
)
echo.
pause
