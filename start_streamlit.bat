@echo off
cd /d "%~dp0"
set Airtable_Base_ID=apppvZnFTV6a33RUf
".venv\Scripts\python.exe" -m streamlit run stripe_streamlit_app.py
pause
