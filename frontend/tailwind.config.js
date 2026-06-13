/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        basin: {
          50: '#f0f4ff',
          100: '#dce6ff',
          500: '#3b5bdb',
          600: '#2f4abf',
          700: '#243aa3',
          900: '#162266',
        },
      },
    },
  },
  plugins: [],
}
