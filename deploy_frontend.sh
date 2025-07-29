#!/bin/bash

# Railway Frontend Deployment Script for YouTube Summary Bot
# This script sets up Railway deployment for the frontend

set -e

echo "🚀 Setting up Railway deployment for frontend..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Please install it first:"
    echo "npm install -g @railway/cli"
    echo "Then run: railway login"
    exit 1
fi

# Check if logged into Railway
if ! railway whoami &> /dev/null; then
    echo "❌ Not logged into Railway. Please run: railway login"
    exit 1
fi

echo "✅ Railway CLI found and authenticated"

# Create/link Railway project
echo "🔗 Linking to Railway project..."
echo "If you haven't created a Railway project yet, please:"
echo "1. Go to https://railway.app"
echo "2. Create a new project"
echo "3. Connect your GitHub repository"
echo "4. Select the 'YouTubeSummary' repository"

# Deploy to Railway
echo "🚀 Deploying frontend to Railway..."
railway up

echo ""
echo "✅ Railway deployment complete!"
echo "🌐 Frontend should be available at your Railway domain"
echo "🔧 Backend continues to run on Heroku: https://yt-bot-backend-8302f5ba3275.herokuapp.com"

echo ""
echo "📝 Next steps:"
echo "1. Check your Railway dashboard for the deployment URL"
echo "2. Verify the frontend connects to the Heroku backend"
echo "3. Test all functionality end-to-end"
