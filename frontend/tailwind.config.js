/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"DM Sans"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['Inter', '"DM Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        panel: '20px',
        '4xl': '24px',
      },
      boxShadow: {
        glass:
          '0 8px 32px rgba(14, 165, 233, 0.08), 0 2px 8px rgba(0, 0, 0, 0.02)',
        'glass-hover':
          '0 16px 40px rgba(14, 165, 233, 0.14), 0 8px 16px rgba(15, 23, 42, 0.06)',
        'glow-sky': '0 12px 36px rgba(14, 165, 233, 0.24)',
      },
      colors: {
        surface: {
          primary: '#F8FCFE',
          secondary: '#EEF8F9',
        },
        accent: {
          sky: '#0EA5E9',
          leaf: '#10B981',
          ink: '#0F172A',
        },
      },
      transitionTimingFunction: {
        standard: 'cubic-bezier(0.4, 0, 0.2, 1)',
        spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      backdropBlur: {
        glass: '16px',
      },
    },
  },
  plugins: [],
}
