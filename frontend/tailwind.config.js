/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0f1e',
          secondary: '#0d1425',
          card: '#111827',
          elevated: '#1a2540',
        },
        accent: {
          DEFAULT: '#f59e0b',
          dim: '#b45309',
        },
        border: {
          DEFAULT: '#1e2d4a',
          bright: '#2a3f6b',
        },
      },
      fontFamily: {
        syne: ['Syne', 'sans-serif'],
        dm: ['DM Sans', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
