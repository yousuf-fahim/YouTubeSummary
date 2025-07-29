import React from 'react'
import { motion } from 'framer-motion'
import { 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  Play, 
  Pause,
  AlertTriangle,
  Zap
} from 'lucide-react'
import { cn, getStatusColor, getStatusBadgeColor } from '@/lib/utils'

interface StatusIndicatorProps {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'processing' | 'active' | 'paused' | 'error'
  label?: string
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
  animated?: boolean
  className?: string
}

export function StatusIndicator({ 
  status, 
  label, 
  showLabel = true, 
  size = 'md', 
  animated = true,
  className 
}: StatusIndicatorProps) {
  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3', 
    lg: 'w-4 h-4'
  }

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5'
  }

  const getIcon = () => {
    switch (status) {
      case 'healthy':
      case 'active':
        return <CheckCircle className={cn(iconSizes[size], 'text-green-500')} />
      case 'processing':
        return <Clock className={cn(iconSizes[size], 'text-yellow-500')} />
      case 'paused':
        return <Pause className={cn(iconSizes[size], 'text-gray-500')} />
      case 'error':
      case 'unhealthy':
        return <AlertCircle className={cn(iconSizes[size], 'text-red-500')} />
      case 'degraded':
        return <AlertTriangle className={cn(iconSizes[size], 'text-yellow-500')} />
      default:
        return <div className={cn(sizeClasses[size], 'rounded-full bg-gray-400')} />
    }
  }

  const getPulseColor = () => {
    switch (status) {
      case 'healthy':
      case 'active':
        return 'bg-green-500'
      case 'processing':
        return 'bg-yellow-500'
      case 'error':
      case 'unhealthy':
        return 'bg-red-500'
      case 'degraded':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="relative">
        {getIcon()}
        {animated && (status === 'processing' || status === 'active') && (
          <motion.div
            className={cn(
              'absolute inset-0 rounded-full opacity-75',
              getPulseColor()
            )}
            animate={{ 
              scale: [1, 1.5, 1],
              opacity: [0.5, 0, 0.5]
            }}
            transition={{ 
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
        )}
      </div>
      {showLabel && (
        <span className={cn('text-sm font-medium', getStatusColor(status))}>
          {label || status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      )}
    </div>
  )
}

interface StatusBadgeProps {
  status: string
  children: React.ReactNode
  className?: string
}

export function StatusBadge({ status, children, className }: StatusBadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      getStatusBadgeColor(status),
      className
    )}>
      {children}
    </span>
  )
}

interface ProgressBarProps {
  value: number
  max?: number
  label?: string
  showPercentage?: boolean
  color?: 'blue' | 'green' | 'yellow' | 'red'
  size?: 'sm' | 'md' | 'lg'
  animated?: boolean
  className?: string
}

export function ProgressBar({ 
  value, 
  max = 100, 
  label, 
  showPercentage = true,
  color = 'blue',
  size = 'md',
  animated = true,
  className 
}: ProgressBarProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)
  
  const sizeClasses = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3'
  }

  const colorClasses = {
    blue: 'bg-blue-600',
    green: 'bg-green-600',
    yellow: 'bg-yellow-600',
    red: 'bg-red-600'
  }

  return (
    <div className={cn('w-full', className)}>
      {(label || showPercentage) && (
        <div className="flex justify-between items-center mb-1">
          {label && (
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
            </span>
          )}
          {showPercentage && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      )}
      <div className={cn(
        'w-full bg-gray-200 rounded-full overflow-hidden dark:bg-gray-700',
        sizeClasses[size]
      )}>
        <motion.div
          className={cn('h-full rounded-full', colorClasses[color])}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ 
            duration: animated ? 0.5 : 0,
            ease: "easeOut"
          }}
        />
      </div>
    </div>
  )
}

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  color?: 'blue' | 'white' | 'gray'
  className?: string
}

export function LoadingSpinner({ size = 'md', color = 'blue', className }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8'
  }

  const colorClasses = {
    blue: 'border-blue-600 border-t-transparent',
    white: 'border-white border-t-transparent',
    gray: 'border-gray-600 border-t-transparent'
  }

  return (
    <motion.div
      className={cn(
        'rounded-full border-2',
        sizeClasses[size],
        colorClasses[color],
        className
      )}
      animate={{ rotate: 360 }}
      transition={{ 
        duration: 1,
        repeat: Infinity,
        ease: "linear"
      }}
    />
  )
}

interface PulsingDotProps {
  color?: 'green' | 'yellow' | 'red' | 'blue' | 'gray'
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function PulsingDot({ color = 'green', size = 'md', className }: PulsingDotProps) {
  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4'
  }

  const colorClasses = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
    blue: 'bg-blue-500',
    gray: 'bg-gray-500'
  }

  return (
    <div className={cn('relative', className)}>
      <motion.div
        className={cn('rounded-full', sizeClasses[size], colorClasses[color])}
        animate={{ 
          scale: [1, 1.2, 1],
          opacity: [1, 0.8, 1]
        }}
        transition={{ 
          duration: 2,
          repeat: Infinity,
          ease: "easeInOut"
        }}
      />
    </div>
  )
}
