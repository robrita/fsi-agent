@echo off
IF NOT EXIST "venv\Scripts\activate" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activate the virtual environment...
call .\venv\Scripts\activate

echo Installing/Updating requirements...
python -m pip install -r requirements.txt

echo Starting app...
streamlit run app.py
chainlit run chainlit.py