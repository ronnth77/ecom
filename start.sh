#!/bin/sh

LOGFILE="/app/logs/startup.log"

mkdir -p /app/logs

echo "" | tee -a $LOGFILE
echo "🚀 FastAPI app starting..." | tee -a $LOGFILE
echo "🌐 Visit: http://localhost:8000" | tee -a $LOGFILE
echo "" | tee -a $LOGFILE

# Start FastAPI with logging
uvicorn main:app --host 0.0.0.0 --port 8000 | tee -a $LOGFILE
