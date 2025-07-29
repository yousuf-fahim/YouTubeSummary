'use client'

import { useState, useEffect, useCallback } from 'react'
import { 
  Play, 
  Plus, 
  Users,
  Activity,
  Settings,
  Youtube,
  AlertCircle
} from 'lucide-react'

// Simple types
interface Channel {
  id: string
  name: string
  added_at?: string
}

interface Summary {
  id?: number
  video_id: string
  title: string
  summary_text?: string
  created_at?: string
  channel?: string
}

interface HealthStatus {
  status: string
  uptime?: string
  version?: string
}

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://yt-bot-backend-8302f5ba3275.herokuapp.com'

export default function WorkingDashboard() {
  // State
  const [activeTab, setActiveTab] = useState('process')
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null)
  const [channels, setChannels] = useState<Channel[]>([])
  const [summaries, setSummaries] = useState<Summary[]>([])
  const [videoUrl, setVideoUrl] = useState('')
  const [newChannelId, setNewChannelId] = useState('')
  const [newChannelName, setNewChannelName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // API calls
  const fetchHealthStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/health`)
      const data = await response.json()
      setHealthStatus(data)
    } catch (err) {
      console.error('Health check failed:', err)
    }
  }, [])

  const fetchChannels = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/channels`)
      const data = await response.json()
      if (data.channels) {
        const channelsList = Object.entries(data.channels).map(([id, info]: [string, any]) => ({
          id,
          name: info.name || id,
          added_at: info.added_at || new Date().toISOString()
        }))
        setChannels(channelsList)
      }
    } catch (err) {
      console.error('Failed to fetch channels:', err)
    }
  }, [])

  const fetchSummaries = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/summaries?limit=20`)
      const data = await response.json()
      if (data.summaries) {
        setSummaries(data.summaries)
      }
    } catch (err) {
      console.error('Failed to fetch summaries:', err)
    }
  }, [])

  const processVideo = async () => {
    if (!videoUrl.trim()) return
    
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${API_BASE}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: videoUrl })
      })
      
      if (response.ok) {
        setVideoUrl('')
        setTimeout(fetchSummaries, 2000) // Refresh summaries after a delay
      } else {
        setError('Failed to process video')
      }
    } catch (err) {
      setError('Error processing video')
    } finally {
      setIsLoading(false)
    }
  }

  const addChannel = async () => {
    if (!newChannelId.trim() || !newChannelName.trim()) return
    
    try {
      const response = await fetch(`${API_BASE}/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          channel_id: newChannelId, 
          channel_name: newChannelName 
        })
      })
      
      if (response.ok) {
        setNewChannelId('')
        setNewChannelName('')
        fetchChannels()
      }
    } catch (err) {
      console.error('Failed to add channel:', err)
    }
  }

  // Effects
  useEffect(() => {
    fetchHealthStatus()
    fetchChannels()
    fetchSummaries()
  }, [fetchHealthStatus, fetchChannels, fetchSummaries])

  // Tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case 'process':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Play className="w-5 h-5" />
                Process YouTube Video
              </h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">YouTube URL</label>
                  <input
                    type="url"
                    value={videoUrl}
                    onChange={(e) => setVideoUrl(e.target.value)}
                    placeholder="https://www.youtube.com/watch?v=..."
                    className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
                    disabled={isLoading}
                  />
                </div>
                
                <button
                  onClick={processVideo}
                  disabled={isLoading || !videoUrl.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-md"
                >
                  <Play className="w-4 h-4" />
                  {isLoading ? 'Processing...' : 'Process Video'}
                </button>
              </div>
            </div>
          </div>
        )
        
      case 'channels':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Plus className="w-5 h-5" />
                Add New Channel
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <input
                  type="text"
                  value={newChannelId}
                  onChange={(e) => setNewChannelId(e.target.value)}
                  placeholder="Channel ID or @handle"
                  className="px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="text"
                  value={newChannelName}
                  onChange={(e) => setNewChannelName(e.target.value)}
                  placeholder="Display name"
                  className="px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <button
                onClick={addChannel}
                disabled={!newChannelId.trim() || !newChannelName.trim()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white rounded-md"
              >
                <Plus className="w-4 h-4" />
                Add Channel
              </button>
            </div>
            
            <div className="bg-white rounded-lg border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Users className="w-5 h-5" />
                Tracked Channels ({channels.length})
              </h3>
              
              {channels.length === 0 ? (
                <p className="text-gray-500 text-center py-4">No channels tracked yet</p>
              ) : (
                <div className="space-y-3">
                  {channels.map((channel) => (
                    <div key={channel.id} className="flex items-center justify-between p-3 border rounded">
                      <div className="flex items-center gap-3">
                        <Youtube className="w-5 h-5 text-red-600" />
                        <div>
                          <div className="font-medium">{channel.name}</div>
                          <div className="text-sm text-gray-500">ID: {channel.id}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )
        
      case 'summaries':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Recent Summaries ({summaries.length})
              </h3>
              
              {summaries.length === 0 ? (
                <p className="text-gray-500 text-center py-4">No summaries yet</p>
              ) : (
                <div className="space-y-4">
                  {summaries.slice(0, 10).map((summary, index) => (
                    <div key={summary.id || index} className="border rounded-lg p-4">
                      <div className="flex items-start gap-3">
                        <div className="w-16 h-12 bg-gray-200 rounded flex items-center justify-center">
                          <Youtube className="w-6 h-6 text-gray-500" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium truncate">{summary.title}</h4>
                          <p className="text-sm text-gray-600 mt-1">
                            {summary.channel && `${summary.channel} • `}
                            {summary.created_at && new Date(summary.created_at).toLocaleDateString()}
                          </p>
                          {summary.summary_text && (
                            <p className="text-sm text-gray-700 mt-2 line-clamp-3">
                              {summary.summary_text.substring(0, 150)}...
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )
        
      case 'settings':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Settings className="w-5 h-5" />
                System Status
              </h3>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span>Backend Status</span>
                  <span className={`px-2 py-1 rounded text-sm ${
                    healthStatus?.status === 'healthy' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {healthStatus?.status || 'Unknown'}
                  </span>
                </div>
                
                {healthStatus?.uptime && (
                  <div className="flex items-center justify-between">
                    <span>Uptime</span>
                    <span className="text-sm text-gray-600">{healthStatus.uptime}</span>
                  </div>
                )}
                
                <div className="flex items-center justify-between">
                  <span>Channels</span>
                  <span className="text-sm text-gray-600">{channels.length} tracked</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span>Summaries</span>
                  <span className="text-sm text-gray-600">{summaries.length} total</span>
                </div>
              </div>
            </div>
          </div>
        )
        
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="container mx-auto p-6 max-w-7xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-red-500 to-purple-600 bg-clip-text text-transparent mb-2">
            YouTube Summary Bot
          </h1>
          <p className="text-slate-600 mb-4">
            AI-powered video summarization with automated Discord reporting
          </p>
          
          <div className="flex items-center justify-center gap-4">
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${
              healthStatus?.status === 'healthy' 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              Backend {healthStatus?.status || 'checking...'}
            </div>
            {healthStatus?.uptime && (
              <span className="text-sm text-slate-500">
                Uptime: {healthStatus.uptime}
              </span>
            )}
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <span className="text-red-700 font-medium">Error</span>
            </div>
            <p className="text-red-600 mt-1">{error}</p>
          </div>
        )}

        {/* Navigation */}
        <div className="mb-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 bg-white rounded-lg p-1 shadow-sm">
            {[
              { id: 'process', label: 'Process Video', icon: Play },
              { id: 'channels', label: `Channels (${channels.length})`, icon: Users },
              { id: 'summaries', label: `Summaries (${summaries.length})`, icon: Activity },
              { id: 'settings', label: 'Settings', icon: Settings }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`
                  flex items-center justify-center gap-2 px-4 py-3 rounded-md 
                  text-sm font-medium transition-colors
                  ${activeTab === id
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }
                `}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        {renderTabContent()}
      </div>
    </div>
  )
}
