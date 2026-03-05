@echo off
chcp 65001 >nul
echo ============================================
echo   4Bro 초기 설정
echo ============================================
echo.

:: Install Python dependencies
echo [..] Python 패키지 설치 중...
pip install -r requirements.txt
echo.

:: Optional: Check Ollama for local fallback
where ollama >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [i] Ollama가 설치되어 있지 않습니다.
    echo     로컬 AI 폴백을 사용하려면 https://ollama.com 에서 설치하세요.
    echo     (Gemini API만 사용할 경우 불필요)
    echo.
) else (
    echo [OK] Ollama 설치 확인됨 (로컬 폴백 사용 가능)
    echo.
)

echo ============================================
echo   설정 완료!
echo.
echo   실행: python src/main.py
echo   빌드: build.bat
echo.
echo   [필수] Gemini API 키를 설정에서 입력하세요.
echo   https://aistudio.google.com/apikey
echo ============================================
pause
