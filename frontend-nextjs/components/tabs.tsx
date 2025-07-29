/**
 * Dashboard Tab Components
 * 
 * Separate components for each tab to maintain code quality and organization
 */

'use client'

import React, { useState } from 'react'
// import { motion } from 'framer-motion'
import { 
  Play, 
  Plus, 
  Trash2, 
  Youtube, 
  Users,
  Settings,
  Activity,
  Zap,
  Globe,
  Database,
  Search,
  Filter,
  Download,
  RefreshCw,
  AlertCircle,
  Copy,
  ExternalLink,
  CheckCircle,
  Clock,
  Calendar
} from 'lucide-react'

import { Channel, Summary, HealthStatus } from '@/lib/api'
import { 
  isValidYouTubeUrl, 
  extractVideoId, 
  formatRelativeTime,
  copyToClipboard 
} from '@/lib/utils'
import { StatusIndicator, ProgressBar, LoadingSpinner } from '@/components/ui/status'
import { VideoList } from '@/components/ui/video-card'

// Types for tab props
interface ProcessingStatus {
  video_id: string
  status: 'processing' | 'completed' | 'error'
  progress: number
  started_at: string
  error_message?: string
}

interface ProcessVideoTabProps {
  videoUrl: string
  isLoading: boolean
  processing: ProcessingStatus[]
  onUrlChange: (url: string) => void
  onProcess: () => void
}

interface ChannelsTabProps {
  channels: Channel[]
  newChannelId: string
  newChannelName: string
  onChannelIdChange: (id: string) => void
  onChannelNameChange: (name: string) => void
  onAddChannel: () => void
  onRemoveChannel: (channelId: string, channelName: string) => void
}

interface SummariesTabProps {
  summaries: Summary[]
  searchQuery: string
  onSearchChange: (query: string) => void
}

interface SettingsTabProps {
  healthStatus: HealthStatus | null
  onTriggerDailyReport: () => void
  onTestDiscord: () => void
  onRefreshData: () => void
}

// Process Video Tab
export function ProcessVideoTab({
  videoUrl,
  isLoading,
  processing,
  onUrlChange,
  onProcess
}: ProcessVideoTabProps) {
  const [urlError, setUrlError] = useState<string | null>(null)

  const handleUrlChange = (value: string) => {
    onUrlChange(value)
    
    // Validate URL
    if (value && !isValidYouTubeUrl(value)) {
      setUrlError('Please enter a valid YouTube URL')
    } else {
      setUrlError(null)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!urlError && videoUrl.trim()) {
      onProcess()
    }
  }

  return (
    <div className="space-y-6">
      {/* Process Video Form */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
          <Play className="w-5 h-5" />
          Process YouTube Video
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="video-url" className="block text-sm font-medium mb-2">
              YouTube URL
            </label>
            <div className="relative">
              <Youtube className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                id="video-url"
                type="url"
                value={videoUrl}
                onChange={(e) => handleUrlChange(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className={`
                  w-full pl-10 pr-4 py-2 border rounded-md 
                  focus:ring-2 focus:ring-blue-500 focus:border-transparent
                  dark:bg-slate-800 dark:border-slate-700 dark:text-white
                  ${urlError ? 'border-red-500' : 'border-gray-300'}
                `}
                disabled={isLoading}
              />
            </div>
            {urlError && (
              <p className="text-red-500 text-sm mt-1">{urlError}</p>
            )}
          </div>
          
          <button
            type="submit"
            disabled={isLoading || !!urlError || !videoUrl.trim()}
            className="
              w-full flex items-center justify-center gap-2 px-4 py-2
              bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400
              text-white font-medium rounded-md transition-colors
            "
          >
            {isLoading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {isLoading ? 'Processing...' : 'Process Video'}
          </button>
        </form>
      </div>

      {/* Processing Queue */}
      {processing.length > 0 && (
        <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
          <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
            <Activity className="w-5 h-5" />
            Processing Queue
          </h3>
          <div className="space-y-4">
            {processing.map((item) => (
              <ProcessingItem key={item.video_id} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* Instructions */}
      <div className="rounded-lg border bg-blue-50 dark:bg-blue-900/20 p-6">
        <h4 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">
          How it works
        </h4>
        <ul className="text-blue-800 dark:text-blue-200 text-sm space-y-1">
          <li>• Paste any YouTube video URL</li>
          <li>• Our AI extracts and summarizes the transcript</li>
          <li>• Summary is automatically posted to Discord</li>
          <li>• Processing typically takes 30-60 seconds</li>
        </ul>
      </div>
    </div>
  )
}

// Processing Item Component
function ProcessingItem({ item }: { item: ProcessingStatus }) {
  const getStatusIcon = () => {
    switch (item.status) {
      case 'processing':
        return <LoadingSpinner size="sm" />
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />
    }
  }

  const getStatusColor = () => {
    switch (item.status) {
      case 'processing': return 'blue'
      case 'completed': return 'green'
      case 'error': return 'red'
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="text-sm font-medium">Video ID: {item.video_id}</span>
        </div>
        <span className="text-xs text-gray-500">
          {formatRelativeTime(item.started_at)}
        </span>
      </div>
      
      <ProgressBar
        value={item.progress}
        color={getStatusColor()}
        showPercentage
      />
      
      {item.error_message && (
        <p className="text-sm text-red-600 dark:text-red-400">
          {item.error_message}
        </p>
      )}
    </div>
  )
}

// Channels Tab
export function ChannelsTab({
  channels,
  newChannelId,
  newChannelName,
  onChannelIdChange,
  onChannelNameChange,
  onAddChannel,
  onRemoveChannel
}: ChannelsTabProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (newChannelId.trim() && newChannelName.trim()) {
      onAddChannel()
    }
  }

  return (
    <div className="space-y-6">
      {/* Add Channel Form */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
          <Plus className="w-5 h-5" />
          Add New Channel
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="channel-id" className="block text-sm font-medium mb-2">
                Channel ID or Handle
              </label>
              <input
                id="channel-id"
                type="text"
                value={newChannelId}
                onChange={(e) => onChannelIdChange(e.target.value)}
                placeholder="@TED or UCsT0YIqwnpJCM-mx7-gSA4Q"
                className="
                  w-full px-3 py-2 border border-gray-300 rounded-md
                  focus:ring-2 focus:ring-blue-500 focus:border-transparent
                  dark:bg-slate-800 dark:border-slate-700 dark:text-white
                "
              />
            </div>
            
            <div>
              <label htmlFor="channel-name" className="block text-sm font-medium mb-2">
                Display Name
              </label>
              <input
                id="channel-name"
                type="text"
                value={newChannelName}
                onChange={(e) => onChannelNameChange(e.target.value)}
                placeholder="TED"
                className="
                  w-full px-3 py-2 border border-gray-300 rounded-md
                  focus:ring-2 focus:ring-blue-500 focus:border-transparent
                  dark:bg-slate-800 dark:border-slate-700 dark:text-white
                "
              />
            </div>
          </div>
          
          <button
            type="submit"
            disabled={!newChannelId.trim() || !newChannelName.trim()}
            className="
              w-full flex items-center justify-center gap-2 px-4 py-2
              bg-green-600 hover:bg-green-700 disabled:bg-gray-400
              text-white font-medium rounded-md transition-colors
            "
          >
            <Plus className="w-4 h-4" />
            Add Channel
          </button>
        </form>
      </div>

      {/* Channels List */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
          <Users className="w-5 h-5" />
          Tracked Channels ({channels.length})
        </h3>
        
        {channels.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No channels tracked yet</p>
            <p className="text-sm">Add a channel above to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {channels.map((channel) => (
              <ChannelItem
                key={channel.id}
                channel={channel}
                onRemove={() => onRemoveChannel(channel.id, channel.name)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Channel Item Component
function ChannelItem({ 
  channel, 
  onRemove 
}: { 
  channel: Channel
  onRemove: () => void 
}) {
  const [showConfirm, setShowConfirm] = useState(false)

  const handleRemove = () => {
    if (showConfirm) {
      onRemove()
      setShowConfirm(false)
    } else {
      setShowConfirm(true)
      setTimeout(() => setShowConfirm(false), 3000)
    }
  }

  return (
    <div className="flex items-center justify-between p-4 border rounded-lg">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center">
          <Youtube className="w-5 h-5 text-red-600" />
        </div>
        <div>
          <div className="font-medium">{channel.name}</div>
          <div className="text-sm text-gray-500">ID: {channel.id}</div>
          <div className="text-xs text-gray-400">
            Added {formatRelativeTime(channel.added_at || new Date().toISOString())}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        <StatusIndicator status="active" size="sm" />
        <button
          onClick={handleRemove}
          className={`
            px-3 py-1 text-sm rounded transition-colors
            ${showConfirm 
              ? 'bg-red-600 text-white hover:bg-red-700' 
              : 'text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20'
            }
          `}
        >
          {showConfirm ? 'Confirm' : 'Remove'}
        </button>
      </div>
    </div>
  )
}

// Summaries Tab
export function SummariesTab({
  summaries,
  searchQuery,
  onSearchChange
}: SummariesTabProps) {
  const [searchInput, setSearchInput] = useState(searchQuery)

  const handleSearchChange = (value: string) => {
    setSearchInput(value)
    onSearchChange(value)
  }

  return (
    <div className="space-y-6">
      {/* Search and Filters */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder="Search summaries..."
                className="
                  w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md
                  focus:ring-2 focus:ring-blue-500 focus:border-transparent
                  dark:bg-slate-800 dark:border-slate-700 dark:text-white
                "
              />
            </div>
          </div>
          
          <div className="flex gap-2">
            <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 dark:border-slate-700 dark:hover:bg-slate-800">
              <Filter className="w-4 h-4" />
              Filter
            </button>
            <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 dark:border-slate-700 dark:hover:bg-slate-800">
              <Download className="w-4 h-4" />
              Export
            </button>
          </div>
        </div>
      </div>

      {/* Summaries List */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
          <Activity className="w-5 h-5" />
          Recent Summaries ({summaries.length})
        </h3>
        
        {summaries.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No summaries yet</p>
            <p className="text-sm">Process a video to see summaries here</p>
          </div>
        ) : (
          <VideoList summaries={summaries} />
        )}
      </div>
    </div>
  )
}

// Settings Tab
export function SettingsTab({
  healthStatus,
  onTriggerDailyReport,
  onTestDiscord,
  onRefreshData
}: SettingsTabProps) {
  return (
    <div className="space-y-6">
      {/* System Status */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
          <Activity className="w-5 h-5" />
          System Status
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium mb-3">Backend Health</h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm">Status</span>
                <StatusIndicator 
                  status={healthStatus?.status || 'unhealthy'} 
                  label={healthStatus?.status || 'Unknown'}
                />
              </div>
              {healthStatus?.uptime && (
                <div className="flex items-center justify-between">
                  <span className="text-sm">Uptime</span>
                  <span className="text-sm text-gray-600">{healthStatus.uptime}</span>
                </div>
              )}
              {healthStatus?.version && (
                <div className="flex items-center justify-between">
                  <span className="text-sm">Version</span>
                  <span className="text-sm text-gray-600">{healthStatus.version}</span>
                </div>
              )}
            </div>
          </div>
          
          <div>
            <h4 className="font-medium mb-3">Services</h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm">Database</span>
                <StatusIndicator status="healthy" size="sm" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Discord Webhooks</span>
                <StatusIndicator status="healthy" size="sm" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">YouTube API</span>
                <StatusIndicator status="healthy" size="sm" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">OpenAI API</span>
                <StatusIndicator status="healthy" size="sm" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
          <Settings className="w-5 h-5" />
          Actions
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            onClick={onTriggerDailyReport}
            className="
              flex items-center justify-center gap-2 px-4 py-3
              bg-blue-600 hover:bg-blue-700 text-white rounded-md
              transition-colors
            "
          >
            <Calendar className="w-4 h-4" />
            Trigger Daily Report
          </button>
          
          <button
            onClick={onTestDiscord}
            className="
              flex items-center justify-center gap-2 px-4 py-3
              bg-purple-600 hover:bg-purple-700 text-white rounded-md
              transition-colors
            "
          >
            <Zap className="w-4 h-4" />
            Test Discord
          </button>
          
          <button
            onClick={onRefreshData}
            className="
              flex items-center justify-center gap-2 px-4 py-3
              border border-gray-300 hover:bg-gray-50 rounded-md
              dark:border-slate-700 dark:hover:bg-slate-800
              transition-colors
            "
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Data
          </button>
          
          <button
            onClick={() => window.open('/api/docs', '_blank')}
            className="
              flex items-center justify-center gap-2 px-4 py-3
              border border-gray-300 hover:bg-gray-50 rounded-md
              dark:border-slate-700 dark:hover:bg-slate-800
              transition-colors
            "
          >
            <ExternalLink className="w-4 h-4" />
            API Documentation
          </button>
        </div>
      </div>

      {/* Configuration */}
      <div className="rounded-lg border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h3 className="flex items-center gap-2 text-lg font-semibold mb-4">
          <Database className="w-5 h-5" />
          Configuration
        </h3>
        
        <div className="space-y-4">
          <div>
            <h4 className="font-medium mb-2">Scheduling</h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Daily reports: 18:00 CEST<br />
              Channel monitoring: Every 30 minutes
            </p>
          </div>
          
          <div>
            <h4 className="font-medium mb-2">Storage</h4>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Primary: Supabase PostgreSQL<br />
              Fallback: Local JSON files
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
