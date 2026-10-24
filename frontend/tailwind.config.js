/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 950: '#0b0e12', 900: '#10141a', 850: '#141920', 800: '#19202a', 700: '#232c38', 600: '#2f3a48', 500: '#4a5869' },
        fog: { 100: '#e8edf3', 300: '#b9c3cf', 400: '#94a1b2', 500: '#6f7d8f' },
        lens: { 300: '#8fe3ee', 400: '#5fd0e0', 500: '#33b6c9', 600: '#1f8fa1' },
        ok: '#5cc98e', warn: '#e9a93c', bad: '#e8646d', info: '#7aa7f5',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', '"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
