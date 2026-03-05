/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Socomep brand — rojo principal
        primary: {
          50:  '#fff1ee',
          100: '#ffddd6',
          200: '#ffb8a8',
          300: '#ff8a6e',
          400: '#ff5731',
          500: '#f02d00',
          600: '#d42400',
          700: '#b01c00',
          800: '#8f1800',
          900: '#6b1200',
          950: '#3d0900',
        },
        // Socomep cyan secundario
        accent: {
          50:  '#e6f9fa',
          100: '#ccf3f6',
          200: '#99e7ed',
          300: '#66dbe4',
          400: '#33cfdb',
          500: '#00b2bd',
          600: '#009aa4',
          700: '#007e87',
          800: '#00636a',
          900: '#00484d',
        },
        // Tono oscuro para sidebar/header
        dark: {
          50:  '#f5f5f5',
          100: '#e9e9e9',
          200: '#d0d0d0',
          300: '#b0b0b0',
          400: '#888888',
          500: '#666666',
          600: '#444444',
          700: '#333333',
          800: '#222222',
          900: '#111111',
          950: '#0a0a0a',
        },
        success: {
          50:  '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
        },
        warning: {
          50:  '#fffbeb',
          100: '#fef3c7',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
        },
        danger: {
          50:  '#fef2f2',
          100: '#fee2e2',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
        },
        info: {
          50:  '#e6f9fa',
          100: '#ccf3f6',
          500: '#00b2bd',
          600: '#009aa4',
          700: '#007e87',
        },
      },
      fontFamily: {
        sans: [
          'Inter Tight',
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Monaco', 'Menlo', 'monospace'],
      },
      boxShadow: {
        'soft':   '0 2px 15px -3px rgba(0,0,0,0.07), 0 10px 20px -2px rgba(0,0,0,0.04)',
        'medium': '0 4px 25px -5px rgba(0,0,0,0.10), 0 10px 30px -5px rgba(0,0,0,0.04)',
        'red':    '0 4px 14px 0 rgba(240,45,0,0.30)',
      },
    },
  },
  plugins: [],
}
