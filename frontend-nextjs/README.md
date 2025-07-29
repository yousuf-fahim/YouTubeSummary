# Next.js Frontend for YouTube Summary Bot

A modern, responsive frontend built with Next.js 15, React 18, Shadcn/ui, and Framer Motion.

## Features

- 🎥 **Video Processing**: Enter YouTube URLs for AI-powered summarization
- 📺 **Channel Management**: Add/remove channels for automatic monitoring
- 📊 **Real-time Dashboard**: View processing status and recent summaries
- ⚡ **Manual Controls**: Trigger daily reports and health checks
- 🎨 **Modern UI**: Beautiful, responsive design with smooth animations
- 🌙 **Dark Mode**: Automatic dark/light mode support

## Quick Start

### 1. Install Dependencies
```bash
cd frontend-nextjs
npm install
```

### 2. Set Environment Variables
Create a `.env.local` file:
```bash
NEXT_PUBLIC_API_URL=https://yt-bot-backend-8302f5ba3275.herokuapp.com
```

### 3. Run Development Server
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Build for Production
```bash
npm run build
npm start
```

## Deployment Options

### Vercel (Recommended)
1. Connect your GitHub repository to Vercel
2. Set environment variable: `NEXT_PUBLIC_API_URL`
3. Deploy automatically on push

### Heroku
1. Create a new Heroku app
2. Set buildpack to Node.js
3. Add environment variables
4. Deploy from Git

### Railway
1. Connect repository to Railway
2. Set environment variables
3. Deploy automatically

## Tech Stack

- **Next.js 15** - React framework with App Router
- **React 18** - Latest React with concurrent features
- **TypeScript** - Type safety and better DX
- **Tailwind CSS** - Utility-first CSS framework
- **Framer Motion** - Smooth animations and transitions
- **Lucide React** - Beautiful, consistent icons

## Project Structure

```
frontend-nextjs/
├── app/                 # Next.js App Router pages
│   ├── layout.tsx      # Root layout
│   ├── page.tsx        # Main dashboard
│   └── globals.css     # Global styles
├── components/         # Reusable UI components
│   └── ui/            # Shadcn/ui components
├── lib/               # Utilities and API client
│   ├── api.ts         # API client and types
│   └── utils.ts       # Helper functions
└── public/            # Static assets
```

## API Integration

The frontend connects to your FastAPI backend at:
`https://yt-bot-backend-8302f5ba3275.herokuapp.com`

### Endpoints Used:
- `GET /health` - Health check and system status
- `POST /process` - Process YouTube videos
- `GET /channels` - List tracked channels
- `POST /channels/add` - Add new channel
- `POST /channels/remove` - Remove channel
- `GET /summaries` - Get recent summaries
- `POST /reports/trigger` - Trigger daily report

## Features Breakdown

### 🎥 Video Processing
- YouTube URL validation and video ID extraction
- Real-time processing status with progress bars
- Automatic refresh of summaries when processing completes

### 📺 Channel Management
- Add channels with ID and display name
- Visual list of all tracked channels
- One-click channel removal

### 📊 Dashboard
- Health status indicator
- Processing queue with live updates
- Recent summaries with expandable content
- System statistics and controls

### ⚙️ Settings
- Manual trigger buttons for testing
- Health check and data refresh
- Direct link to API documentation
- System status overview

## Performance Features

- **Route-based code splitting** for faster loads
- **Optimized images** with Next.js Image component
- **Automatic caching** of API responses
- **Smooth animations** with Framer Motion
- **Responsive design** for all screen sizes

## Development

### Adding New Features
1. Create components in `components/` directory
2. Add API methods to `lib/api.ts`
3. Update types and interfaces as needed
4. Test with development server

### Styling Guidelines
- Use Tailwind utility classes
- Follow dark/light mode patterns
- Maintain consistent spacing and typography
- Use Framer Motion for animations

## Troubleshooting

### Common Issues

**"Cannot find module" errors**: Run `npm install` to install dependencies

**API connection failed**: Check if backend is running and `NEXT_PUBLIC_API_URL` is correct

**Build errors**: Ensure all TypeScript types are properly defined

**Styling issues**: Make sure Tailwind CSS is properly configured

### Environment Variables
- `NEXT_PUBLIC_API_URL` - Backend API URL (required)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details
