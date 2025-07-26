#!/bin/bash

# Railway Start Script for Frontend
echo "🚀 Starting YouTube Summary Bot Frontend..."

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
