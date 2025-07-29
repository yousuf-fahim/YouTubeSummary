#!/bin/bash
# Railway startup script for YouTube Summary Bot Frontend

echo "🚀 Starting YouTube Summary Bot Frontend on Railway..."
echo "🔗 Backend URL: $BACKEND_URL"
echo "🌐 Port: $PORT"

# Navigate to frontend directory
cd frontend

# Install any missing dependencies
pip install --no-cache-dir -r requirements.txt

# Start Streamlit with Railway-specific configuration
exec streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
