@echo off
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Starting Multiplayer Client...
python -m game.network.client

echo.
pause
