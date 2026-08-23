#!/bin/bash
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
exec uvicorn app:app --host 127.0.0.1 --port 8777 --workers 1 --loop asyncio --timeout-keep-alive 30
