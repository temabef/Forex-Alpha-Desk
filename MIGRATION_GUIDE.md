# Nautilus Engine - VPS Migration Guide

This document outlines the exact steps required to set up the Nautilus Engine on a brand new Virtual Private Server (VPS / RDP).

## 1. Initial Software Setup
1. **Download and Install MetaTrader 5 (MT5):** 
   - Install the terminal provided by your Prop Firm.
   - Log into your trading account.
   - Go to `Tools > Options > Expert Advisors` and check **"Allow algorithmic trading"**.
2. **Download and Install Python:**
   - Download Python (3.9 or higher) for Windows.
   - **CRITICAL:** During the installation screen, you MUST check the box at the bottom that says **"Add Python to PATH"** before clicking Install.

## 2. Clone the Repository
1. Open Command Prompt (`cmd`) or PowerShell.
2. Navigate to your Documents folder: `cd Documents`
3. Clone your private repository: 
   `git clone https://github.com/temabef/Forex-Alpha-Desk.git`
4. Enter the folder: `cd Forex-Alpha-Desk`

## 3. Install Dependencies
1. While inside the `Forex-Alpha-Desk` folder in the terminal, create a virtual environment (optional but recommended):
   `python -m venv venv`
2. Activate the virtual environment:
   `venv\Scripts\activate`
3. Install the required packages:
   `pip install -r requirements.txt`

## 4. Environment Variables (.env)
Because `.env` files contain sensitive API keys and secrets, they are intentionally ignored by Git and will not exist when you clone the repo.
1. Create a new file named `.env` in the root folder of your project.
2. Paste your configuration into it. Example format:
   ```text
   TELEGRAM_TOKEN=your_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   MT5_TERMINAL_PATH=C:\Program Files\Your MT5 Terminal\terminal64.exe
   LOT_SIZE_AI=0.05
   LOT_SIZE_PAIRS=0.02
   LOT_SIZE_TREND=0.04
   SYMBOL_SUFFIX=.x
   ENABLE_NEWS_FILTER=True
   ENABLE_FRIDAY_EXIT=False
   MAX_DAILY_DRAWDOWN_PCT=0.035
   NEWS_BUFFER_MINUTES=30
   ```
3. Make absolutely sure the `MT5_TERMINAL_PATH` exactly matches the installation path on your new PC.

## 5. Automation Setup (Task Scheduler)
1. Open the Windows **Task Scheduler**.
2. Click **Create Task...** on the right side.
3. **General Tab:** Name it `Nautilus Bot`. Check "Run whether user is logged on or not".
4. **Triggers Tab:** Click New. Set it to Daily, repeat task every 1 hour, indefinitely.
5. **Actions Tab:** Click New. 
   - Action: Start a program.
   - Program/script: Browse to your Python executable (e.g., `C:\Users\Administrator\Documents\Forex-Alpha-Desk\venv\Scripts\python.exe`).
   - Add arguments: `get_current_signal.py`
   - Start in: The full path to your folder (e.g., `C:\Users\Administrator\Documents\Forex-Alpha-Desk`).
6. Save the task and enter your Windows administrator password.

Your Nautilus Engine is now fully migrated and operational on the new VPS!
