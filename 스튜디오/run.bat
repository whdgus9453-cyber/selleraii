@echo off
chcp 65001 >nul
cd /d "c:\Users\ljs90\OneDrive\바탕 화면\새 폴더"
title ⚡ SellerAI Studio

echo ===================================================
echo ⚡ SellerAI Studio 실행 중...
echo ===================================================

:: 포트 8501 실행 여부 확인
netstat -ano | findstr ":8501" | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/2] 서버 시작 중... 잠시만 기다려주세요...
    start "SellerAI_Server" /min cmd /c "python -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"
    timeout /t 3 /nobreak >nul
) else (
    echo [안내] 서버가 이미 실행 중입니다. 브라우저로 바로 연결합니다!
)

echo [2/2] 브라우저 화면 여는 중: http://localhost:8501
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" "http://localhost:8501"
) else (
    start "" "http://localhost:8501"
)
exit
