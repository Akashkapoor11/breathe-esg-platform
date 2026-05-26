/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Space Grotesk', 'sans-serif'],
      },
      colors: {
        carbon: {
          50:  '#eefaf3',
          100: '#d5f3e2',
          200: '#aee7c8',
          300: '#79d3a7',
          400: '#45b882',
          500: '#229c68',
          600: '#157d53',
          700: '#116444',
          800: '#0f5038',
          900: '#0d4130',
          950: '#06241a',
        },
      },
    },
  },
  plugins: [],
}
