@echo off
echo ============================================
echo  Genna Content Machine — Setup
echo ============================================
echo.

REM 1. Create virtual environment
echo [1/4] Creating virtual environment...
python -m venv .venv
echo      Done!
echo.

REM 2. Activate venv
echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat
echo      Done!
echo.

REM 3. Install dependencies
echo [3/4] Installing dependencies...
pip install -r requirements.txt
echo      Done!
echo.

REM 4. Create .env from example
echo [4/4] Setting up environment file...
if not exist .env (
    copy .env.example .env
    echo      Created .env from .env.example
    echo      IMPORTANT: Open .env and add your API keys!
) else (
    echo      .env already exists, skipping.
)
echo.

echo ============================================
echo  Setup complete!
echo.
echo  Next steps:
echo    1. Open .env and add your API keys
echo    2. Activate venv: .venv\Scripts\activate
echo    3. Run scripts from the scripts/ folder
echo ============================================
pause
