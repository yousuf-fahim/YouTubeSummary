#!/bin/bash

# Railway Root Start Script - Frontend Deployment
echo "🚀 Starting from root directory..."
echo "📂 Current directory: $(pwd)"
echo "📂 Contents: $(ls -la)"

# Navigate to frontend directory
cd frontend

echo "📂 Switched to frontend directory: $(pwd)"
echo "📊 App.py exists: $(test -f app.py && echo 'YES' || echo 'NO')"

if [ -f app.py ]; then
    echo "📊 App.py line count: $(wc -l < app.py)"
fi

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
