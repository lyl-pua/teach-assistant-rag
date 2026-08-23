@echo off
cd /d %~dp0
uvicorn app:app --host 127.0.0.1 --port 8777 --reload
