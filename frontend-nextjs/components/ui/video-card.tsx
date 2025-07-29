import React from 'react'
import { motion } from 'framer-motion'
import { ExternalLink, Copy, Eye, Clock, Calendar, Youtube } from 'lucide-react'
import { 
  extractVideoId, 
  getYoutubeThumbnail, 
  formatDate, 
  formatRelativeTime, 
  truncateText, 
  copyToClipboard 
} from '@/lib/utils'
import { Summary } from '@/lib/api'
import { StatusBadge } from './status'

interface VideoCardProps {
  summary: Summary
  compact?: boolean
  showThumbnail?: boolean
  className?: string
  onView?: (summary: Summary) => void
}

export function VideoCard({ 
  summary, 
  compact = false, 
  showThumbnail = true,
  className,
  onView 
}: VideoCardProps) {
  const videoId = extractVideoId(summary.video_url || '') || summary.video_id
  const thumbnailUrl = videoId ? getYoutubeThumbnail(videoId) : null

  const handleCopyUrl = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (summary.video_url) {
      const success = await copyToClipboard(summary.video_url)
      if (success) {
        // Show toast notification
        console.log('URL copied to clipboard')
      }
    }
  }

  const handleOpenYoutube = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (summary.video_url) {
      window.open(summary.video_url, '_blank')
    }
  }

  if (compact) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`
          flex items-center gap-3 p-3 bg-white dark:bg-slate-800 
          rounded-lg border border-slate-200 dark:border-slate-700
          hover:shadow-md transition-shadow cursor-pointer
          ${className}
        `}
        onClick={() => onView?.(summary)}
      >
        {showThumbnail && thumbnailUrl && (
          <img
            src={thumbnailUrl}
            alt={summary.title}
            className="w-16 h-12 object-cover rounded flex-shrink-0"
            loading="lazy"
          />
        )}
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-sm truncate">{summary.title}</h4>
          <div className="flex items-center gap-2 mt-1">
            {summary.channel && (
              <span className="text-xs text-slate-500">{summary.channel}</span>
            )}
            {summary.created_at && (
              <span className="text-xs text-slate-400">
                {formatRelativeTime(summary.created_at)}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleOpenYoutube}
            className="p-1 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
            title="Open in YouTube"
          >
            <ExternalLink className="w-4 h-4 text-slate-400" />
          </button>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`
        bg-white dark:bg-slate-800 rounded-lg border border-slate-200 
        dark:border-slate-700 overflow-hidden hover:shadow-lg 
        transition-shadow cursor-pointer
        ${className}
      `}
      onClick={() => onView?.(summary)}
    >
      {showThumbnail && thumbnailUrl && (
        <div className="relative">
          <img
            src={thumbnailUrl}
            alt={summary.title}
            className="w-full h-48 object-cover"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-black bg-opacity-0 hover:bg-opacity-10 transition-opacity flex items-center justify-center">
            <Youtube className="w-8 h-8 text-white opacity-0 hover:opacity-100 transition-opacity" />
          </div>
        </div>
      )}
      
      <div className="p-6">
        <div className="flex items-start justify-between gap-3 mb-3">
          <h3 className="font-semibold text-lg leading-tight">{summary.title}</h3>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={handleCopyUrl}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-full transition-colors"
              title="Copy URL"
            >
              <Copy className="w-4 h-4 text-slate-400" />
            </button>
            <button
              onClick={handleOpenYoutube}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-full transition-colors"
              title="Open in YouTube"
            >
              <ExternalLink className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>

        {summary.channel && (
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
              {summary.channel}
            </span>
            {summary.channel_id && (
              <StatusBadge status="active">
                Tracked Channel
              </StatusBadge>
            )}
          </div>
        )}

        {(summary.summary_text || summary.content) && (
          <p className="text-slate-600 dark:text-slate-300 text-sm leading-relaxed mb-4">
            {truncateText(summary.summary_text || summary.content || '', 200)}
          </p>
        )}

        <div className="flex items-center justify-between text-sm text-slate-500">
          <div className="flex items-center gap-4">
            {summary.created_at && (
              <div className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                <span>{formatRelativeTime(summary.created_at)}</span>
              </div>
            )}
            {summary.transcript_length && (
              <span>{Math.round(summary.transcript_length / 1000)}k chars</span>
            )}
          </div>
          
          <button
            onClick={(e) => {
              e.stopPropagation()
              onView?.(summary)
            }}
            className="flex items-center gap-1 px-3 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
          >
            <Eye className="w-4 h-4" />
            <span>View Details</span>
          </button>
        </div>
      </div>
    </motion.div>
  )
}

interface VideoListProps {
  summaries: Summary[]
  loading?: boolean
  compact?: boolean
  limit?: number
  onLoadMore?: () => void
  onViewSummary?: (summary: Summary) => void
  className?: string
}

export function VideoList({ 
  summaries, 
  loading = false, 
  compact = false,
  limit,
  onLoadMore,
  onViewSummary,
  className 
}: VideoListProps) {
  const displayedSummaries = limit ? summaries.slice(0, limit) : summaries
  const hasMore = limit && summaries.length > limit

  if (loading && summaries.length === 0) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="animate-pulse">
            <div className="bg-slate-200 dark:bg-slate-700 rounded-lg h-32"></div>
          </div>
        ))}
      </div>
    )
  }

  if (summaries.length === 0) {
    return (
      <div className="text-center py-12">
        <Youtube className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-slate-500 mb-2">No summaries yet</h3>
        <p className="text-slate-400">
          Process some YouTube videos to see summaries here
        </p>
      </div>
    )
  }

  return (
    <div className={className}>
      <div className={compact ? 'space-y-2' : 'grid gap-6 md:grid-cols-2 lg:grid-cols-3'}>
        {displayedSummaries.map((summary, index) => (
          <VideoCard
            key={summary.id || summary.video_id || index}
            summary={summary}
            compact={compact}
            onView={onViewSummary}
          />
        ))}
      </div>
      
      {hasMore && (
        <div className="mt-6 text-center">
          <button
            onClick={onLoadMore}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            disabled={loading}
          >
            {loading ? 'Loading...' : `Load More (${summaries.length - limit!} remaining)`}
          </button>
        </div>
      )}
    </div>
  )
}
