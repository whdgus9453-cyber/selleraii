@echo off
chcp 65001 > nul
title AI 상세페이지 & 미디어 스튜디오

cd /d "%~dp0"

echo ===================================================
echo   🚀 AI 상세페이지 & 미디어 스튜디오 실행 중...
echo ===================================================
echo.

:: 포트 8501 활성화 확인
netstat -ano | findstr :8501 > nul
if %errorlevel% equ 0 (
    echo [안내] 앱 서버가 이미 실행 중입니다. 브라우저로 연결합니다!
    start http://localhost:8501
    exit /b 0
)

tasklist | findstr /i "cloudflared" >nul 2>&1
if %errorlevel% neq 0 (
    start "SellerAI_Tunnel" /min cmd /c "python start_tunnel.py"
)

echo [1/2] 서버 초기화 및 구동 중...
echo [2/2] 잠시 후 브라우저가 자동으로 열립니다: http://localhost:8501
echo.

timeout /t 2 /nobreak > nul
start "" "http://localhost:8501"

python -m streamlit run app.py --server.port=8501 --server.headless=true

if %errorlevel% neq 0 (
    echo.
    echo [오류] 서버 실행 중 문제가 발생했습니다. 창을 닫기 전 위 메시지를 확인해주세요.
    pause
)
