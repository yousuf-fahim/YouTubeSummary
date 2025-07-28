#!/bin/bash

# Railway Start Script for Frontend v3.2 - FIXED AUTOMATION
echo "🚀 Starting YouTube Summary Bot Frontend (Railway v3.2)..."
echo "📊 Current directory: $(pwd)"
echo "📊 App.py line count: $(wc -l < app.py)"

# Set default port if not provided
export PORT=${PORT:-8501}

# Start Streamlit with Railway-compatible settings
exec streamlit run app.py \
  --server.port=$PORT \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false
