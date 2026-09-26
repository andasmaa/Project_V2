/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'attijari': {
          'blue': '#0A2B4E',
          'gold': '#D4AF37',
        }
      },
    },
  },
  plugins: [],
}