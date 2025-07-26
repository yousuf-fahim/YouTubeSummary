#!/bin/bash
set -e

echo "🚀 Starting YouTube Summary Bot..."
echo "📂 Working directory: $(pwd)"
echo "📂 Directory contents:"
ls -la

# Navigate to frontend directory
if [ -d "frontend" ]; then
    cd frontend
    echo "✅ Changed to frontend directory: $(pwd)"
else
    echo "❌ Frontend directory not found!"
    exit 1
fi

# Verify app.py exists
if [ -f "app.py" ]; then
    echo "✅ Found app.py ($(wc -l < app.py) lines)"
else
    echo "❌ app.py not found!"
    exit 1
fi

# Set port from Railway environment
export PORT=${PORT:-8501}
echo "🌐 Starting Streamlit on port $PORT"

# Start Streamlit
exec streamlit run app.py \
  --server.port=$PORT \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false
