@echo off
title Aura Rec — grabadora de pantalla
cd /d "%~dp0"
"C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe" "%~dp0aura-rec.py"
if errorlevel 1 pause
