#!/bin/bash

# Heroku Deployment Script for YouTube Summary Bot Backend
# This script creates a clean deployment structure for Heroku

set -e

echo "🚀 Preparing backend deployment..."

# Create deployment directory
DEPLOY_DIR="backend_deploy"
rm -rf $DEPLOY_DIR
mkdir -p $DEPLOY_DIR

echo "📁 Copying backend files..."
cp backend/main.py $DEPLOY_DIR/
cp backend/Procfile $DEPLOY_DIR/
cp backend/requirements.txt $DEPLOY_DIR/

echo "📁 Copying shared modules..."
cp -r shared $DEPLOY_DIR/

echo "🔧 Adding Python version file for Heroku..."
echo "3.11" > $DEPLOY_DIR/.python-version

echo "✅ Deployment directory prepared: $DEPLOY_DIR"
echo "📝 Contents:"
ls -la $DEPLOY_DIR

echo ""
echo "� Deploying to Heroku..."
cd $DEPLOY_DIR
git init
git add .
git commit -m "Deploy backend with shared modules - $(date)"
heroku git:remote -a yt-bot-backend
git push heroku main --force

echo ""
echo "✅ Deployment complete!"
echo "🔗 Testing deployment..."
sleep 5
curl -s "https://yt-bot-backend-8302f5ba3275.herokuapp.com/health" | head -10

echo ""
echo "🎯 Backend deployment finished"
