/**
 * Validate email format
 */
export const isValidEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

/**
 * Validate Chilean phone number
 */
export const isValidChileanPhone = (phone: string): boolean => {
  // Remove non-numeric characters
  const cleaned = phone.replace(/\D/g, '')

  // Check for valid formats:
  // - 9 digits starting with 9 (mobile)
  // - 11 digits starting with 56 (with country code)
  if (cleaned.length === 9 && cleaned.startsWith('9')) {
    return true
  }
  if (cleaned.length === 11 && cleaned.startsWith('56')) {
    return true
  }

  return false
}

/**
 * Validate Chilean RUT
 */
export const isValidRUT = (rut: string): boolean => {
  if (!rut) return false

  // Remove dots and hyphen
  const cleaned = rut.replace(/[.-]/g, '').toUpperCase()

  if (cleaned.length < 2) return false

  const body = cleaned.slice(0, -1)
  const dv = cleaned.slice(-1)

  // Calculate verification digit
  let sum = 0
  let multiplier = 2

  for (let i = body.length - 1; i >= 0; i--) {
    sum += parseInt(body[i], 10) * multiplier
    multiplier = multiplier === 7 ? 2 : multiplier + 1
  }

  const remainder = 11 - (sum % 11)
  let calculatedDV: string

  if (remainder === 11) {
    calculatedDV = '0'
  } else if (remainder === 10) {
    calculatedDV = 'K'
  } else {
    calculatedDV = String(remainder)
  }

  return calculatedDV === dv
}

/**
 * Validate password strength
 */
export const validatePassword = (password: string): {
  isValid: boolean
  errors: string[]
} => {
  const errors: string[] = []

  if (password.length < 8) {
    errors.push('La contraseña debe tener al menos 8 caracteres')
  }

  if (!/[A-Z]/.test(password)) {
    errors.push('Debe incluir al menos una letra mayúscula')
  }

  if (!/[a-z]/.test(password)) {
    errors.push('Debe incluir al menos una letra minúscula')
  }

  if (!/[0-9]/.test(password)) {
    errors.push('Debe incluir al menos un número')
  }

  return {
    isValid: errors.length === 0,
    errors,
  }
}

/**
 * Validate that a value is within a range
 */
export const isInRange = (value: number, min: number, max: number): boolean => {
  return value >= min && value <= max
}

/**
 * Validate required field
 */
export const isRequired = (value: unknown): boolean => {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  return true
}

/**
 * Validate minimum length
 */
export const hasMinLength = (value: string, minLength: number): boolean => {
  return value.length >= minLength
}

/**
 * Validate maximum length
 */
export const hasMaxLength = (value: string, maxLength: number): boolean => {
  return value.length <= maxLength
}

/**
 * Validate that coordinates are within Rancagua area
 */
export const isInRancaguaArea = (lat: number, lng: number): boolean => {
  // Rancagua bounding box (approximate)
  const bounds = {
    minLat: -34.25,
    maxLat: -34.10,
    minLng: -70.80,
    maxLng: -70.65,
  }

  return (
    lat >= bounds.minLat &&
    lat <= bounds.maxLat &&
    lng >= bounds.minLng &&
    lng <= bounds.maxLng
  )
}
