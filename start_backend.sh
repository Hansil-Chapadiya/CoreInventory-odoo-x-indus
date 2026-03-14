#!/bin/bash
# Quick start script for CoreInventory Backend

cd "$(dirname "$0")/backend"

echo "🚀 Starting CoreInventory Backend..."
echo "📦 Database: Neon PostgreSQL (already configured)"
echo "🔌 Port: 8000"
echo ""
echo "✅ API Docs: http://localhost:8000/docs"
echo "✅ ReDoc: http://localhost:8000/redoc"
echo "✅ Health Check: http://localhost:8000/health"
echo ""
echo "Press CTRL+C to stop"
echo ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
