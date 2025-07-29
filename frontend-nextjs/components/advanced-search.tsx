'use client'

import React, { useState, useMemo } from 'react'
import { Search, Filter, Calendar, User, Tag, X, SlidersHorizontal } from 'lucide-react'

interface FilterOptions {
  search: string
  channel: string
  dateRange: 'all' | 'today' | 'week' | 'month' | 'year'
  sortBy: 'newest' | 'oldest' | 'title' | 'channel'
  tags: string[]
}

interface Summary {
  id?: number
  video_id: string
  title: string
  summary_text?: string
  created_at?: string
  channel?: string
  tags?: string[]
}

interface AdvancedSearchProps {
  summaries: Summary[]
  channels: string[]
  onFilteredResults: (filtered: Summary[]) => void
  className?: string
}

export default function AdvancedSearch({ 
  summaries, 
  channels, 
  onFilteredResults, 
  className = '' 
}: AdvancedSearchProps) {
  const [filters, setFilters] = useState<FilterOptions>({
    search: '',
    channel: '',
    dateRange: 'all',
    sortBy: 'newest',
    tags: []
  })
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Get all unique tags from summaries
  const allTags = useMemo(() => {
    const tagSet = new Set<string>()
    summaries.forEach(summary => {
      summary.tags?.forEach(tag => tagSet.add(tag))
    })
    return Array.from(tagSet)
  }, [summaries])

  // Filter and sort summaries
  const filteredSummaries = useMemo(() => {
    let filtered = summaries.filter(summary => {
      // Search filter
      if (filters.search) {
        const searchLower = filters.search.toLowerCase()
        const matchesTitle = summary.title.toLowerCase().includes(searchLower)
        const matchesSummary = summary.summary_text?.toLowerCase().includes(searchLower)
        if (!matchesTitle && !matchesSummary) return false
      }

      // Channel filter
      if (filters.channel && summary.channel !== filters.channel) {
        return false
      }

      // Date range filter
      if (filters.dateRange !== 'all' && summary.created_at) {
        const summaryDate = new Date(summary.created_at)
        const now = new Date()
        const diffDays = Math.floor((now.getTime() - summaryDate.getTime()) / (1000 * 60 * 60 * 24))

        switch (filters.dateRange) {
          case 'today':
            if (diffDays > 0) return false
            break
          case 'week':
            if (diffDays > 7) return false
            break
          case 'month':
            if (diffDays > 30) return false
            break
          case 'year':
            if (diffDays > 365) return false
            break
        }
      }

      // Tags filter
      if (filters.tags.length > 0 && summary.tags) {
        const hasMatchingTag = filters.tags.some(tag => summary.tags?.includes(tag))
        if (!hasMatchingTag) return false
      }

      return true
    })

    // Sort results
    filtered.sort((a, b) => {
      switch (filters.sortBy) {
        case 'newest':
          return new Date(b.created_at || '').getTime() - new Date(a.created_at || '').getTime()
        case 'oldest':
          return new Date(a.created_at || '').getTime() - new Date(b.created_at || '').getTime()
        case 'title':
          return a.title.localeCompare(b.title)
        case 'channel':
          return (a.channel || '').localeCompare(b.channel || '')
        default:
          return 0
      }
    })

    return filtered
  }, [summaries, filters])

  // Update parent component when filters change
  React.useEffect(() => {
    onFilteredResults(filteredSummaries)
  }, [filteredSummaries, onFilteredResults])

  const updateFilter = (key: keyof FilterOptions, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const addTag = (tag: string) => {
    if (!filters.tags.includes(tag)) {
      updateFilter('tags', [...filters.tags, tag])
    }
  }

  const removeTag = (tag: string) => {
    updateFilter('tags', filters.tags.filter(t => t !== tag))
  }

  const clearAllFilters = () => {
    setFilters({
      search: '',
      channel: '',
      dateRange: 'all',
      sortBy: 'newest',
      tags: []
    })
  }

  const hasActiveFilters = filters.search || filters.channel || filters.dateRange !== 'all' || filters.tags.length > 0

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
        <input
          type="text"
          placeholder="Search summaries by title or content..."
          value={filters.search}
          onChange={(e) => updateFilter('search', e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Filter Toggle */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 transition-colors"
        >
          <SlidersHorizontal className="w-4 h-4" />
          Advanced Filters
          {hasActiveFilters && (
            <span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">
              {[filters.search, filters.channel, filters.dateRange !== 'all', filters.tags.length > 0]
                .filter(Boolean).length}
            </span>
          )}
        </button>

        {hasActiveFilters && (
          <button
            onClick={clearAllFilters}
            className="text-sm text-red-600 hover:text-red-800 transition-colors"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Advanced Filters */}
      {showAdvanced && (
        <div className="bg-gray-50 rounded-lg p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Channel Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Channel
              </label>
              <select
                value={filters.channel}
                onChange={(e) => updateFilter('channel', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All channels</option>
                {channels.map(channel => (
                  <option key={channel} value={channel}>{channel}</option>
                ))}
              </select>
            </div>

            {/* Date Range */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Date Range
              </label>
              <select
                value={filters.dateRange}
                onChange={(e) => updateFilter('dateRange', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All time</option>
                <option value="today">Today</option>
                <option value="week">This week</option>
                <option value="month">This month</option>
                <option value="year">This year</option>
              </select>
            </div>

            {/* Sort By */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Sort By
              </label>
              <select
                value={filters.sortBy}
                onChange={(e) => updateFilter('sortBy', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="title">Title A-Z</option>
                <option value="channel">Channel A-Z</option>
              </select>
            </div>
          </div>

          {/* Tags */}
          {allTags.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Tags
              </label>
              <div className="flex flex-wrap gap-2">
                {allTags.map(tag => (
                  <button
                    key={tag}
                    onClick={() => filters.tags.includes(tag) ? removeTag(tag) : addTag(tag)}
                    className={`px-3 py-1 rounded-full text-sm transition-colors ${
                      filters.tags.includes(tag)
                        ? 'bg-blue-100 text-blue-800 border border-blue-200'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-200'
                    }`}
                  >
                    <Tag className="w-3 h-3 inline mr-1" />
                    {tag}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Active Tags */}
          {filters.tags.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Active Filters
              </label>
              <div className="flex flex-wrap gap-2">
                {filters.tags.map(tag => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                  >
                    {tag}
                    <button
                      onClick={() => removeTag(tag)}
                      className="hover:bg-blue-200 rounded-full p-0.5"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Results Summary */}
      <div className="text-sm text-gray-600">
        {filteredSummaries.length === summaries.length ? (
          `Showing all ${summaries.length} summaries`
        ) : (
          `Showing ${filteredSummaries.length} of ${summaries.length} summaries`
        )}
      </div>
    </div>
  )
}
