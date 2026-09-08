/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        octo: {
          orange: '#C65D3A',
          'orange-hover': '#B2502F',
          'orange-light': '#FBF1ED',
          bg: '#F7F4EE',
          surface: '#FFFFFF',
          'surface-warm': '#EFE9DF',
          charcoal: '#252525',
          muted: '#6F6A63',
          border: '#DED8CE',
        },
      },
      borderRadius: {
        'btn': '12px',
        'card': '16px',
      },
    },
  },
  plugins: [],
}
