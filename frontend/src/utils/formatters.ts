import { format, formatDistance as dateFnsFormatDistance, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'

/**
 * Format a date string to a localized date
 */
export const formatDate = (date: string | Date, pattern = 'dd MMM yyyy'): string => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date
  return format(dateObj, pattern, { locale: es })
}

/**
 * Format a date string to a localized date and time
 */
export const formatDateTime = (date: string | Date, pattern = "dd MMM yyyy 'a las' HH:mm"): string => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date
  return format(dateObj, pattern, { locale: es })
}

/**
 * Format a date string to time only
 */
export const formatTime = (date: string | Date): string => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date
  return format(dateObj, 'HH:mm', { locale: es })
}

/**
 * Format a date string to relative time (e.g., "hace 5 minutos")
 */
export const formatRelativeTime = (date: string | Date): string => {
  const dateObj = typeof date === 'string' ? parseISO(date) : date
  return dateFnsFormatDistance(dateObj, new Date(), { addSuffix: true, locale: es })
}

/**
 * Format a number to Chilean Peso currency
 */
export const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

/**
 * Format a number with thousands separator
 */
export const formatNumber = (value: number, decimals = 0): string => {
  return new Intl.NumberFormat('es-CL', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/**
 * Format a percentage
 */
export const formatPercent = (value: number, decimals = 0): string => {
  return `${formatNumber(value, decimals)}%`
}

/**
 * Format distance in kilometers
 */
export const formatDistance = (km: number): string => {
  if (km < 1) {
    return `${Math.round(km * 1000)} m`
  }
  return `${km.toFixed(1)} km`
}

/**
 * Format duration in minutes to human readable
 */
export const formatDuration = (minutes: number): string => {
  if (minutes < 60) {
    return `${minutes} min`
  }
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (mins === 0) {
    return `${hours} h`
  }
  return `${hours} h ${mins} min`
}

/**
 * Format phone number (Chilean format)
 */
export const formatPhone = (phone: string): string => {
  // Remove non-numeric characters
  const cleaned = phone.replace(/\D/g, '')

  // Check if it starts with 56 (country code)
  if (cleaned.startsWith('56') && cleaned.length === 11) {
    return `+56 ${cleaned.slice(2, 3)} ${cleaned.slice(3, 7)} ${cleaned.slice(7)}`
  }

  // Format 9-digit mobile number
  if (cleaned.length === 9 && cleaned.startsWith('9')) {
    return `+56 ${cleaned.slice(0, 1)} ${cleaned.slice(1, 5)} ${cleaned.slice(5)}`
  }

  return phone
}

/**
 * Truncate text to a maximum length
 */
export const truncate = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 3)}...`
}
