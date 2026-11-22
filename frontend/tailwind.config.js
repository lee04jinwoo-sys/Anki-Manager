/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'media', // dark: variants follow the system setting, like the apple-* variables
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"LXGW WenKai GB"',
          '"霞鹜文楷 GB"',
          '"SF Pro Text"',
          '"SF Pro Display"',
          '"Helvetica Neue"',
          "Inter",
          "Arial",
          "sans-serif",
        ],
        chinese: [
          '"LXGW WenKai GB"',
          '"霞鹜文楷 GB"',
          '"Kaiti SC"',
          '"STKaiti"',
          '"PingFang SC"',
          "sans-serif",
        ],
        mono: [
          '"SF Mono"',
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      // Every apple-* color is a CSS variable (RGB triplet) set per color scheme in src/index.css,
      // so the whole UI follows the system light/dark setting.
      colors: {
        apple: {
          bg: 'rgb(var(--apple-bg) / <alpha-value>)',
          card: 'rgb(var(--apple-card) / <alpha-value>)',
          subtle: 'rgb(var(--apple-subtle) / <alpha-value>)',
          subtleHover: 'rgb(var(--apple-subtle-hover) / <alpha-value>)',
          border: 'rgb(var(--apple-border) / <alpha-value>)',
          borderStrong: 'rgb(var(--apple-border-strong) / <alpha-value>)',
          text: 'rgb(var(--apple-text) / <alpha-value>)',
          secondary: 'rgb(var(--apple-secondary) / <alpha-value>)',
          blue: 'rgb(var(--apple-blue) / <alpha-value>)',
          blueHover: 'rgb(var(--apple-blue-hover) / <alpha-value>)',
          green: 'rgb(var(--apple-green) / <alpha-value>)',
          orange: 'rgb(var(--apple-orange) / <alpha-value>)',
          red: 'rgb(var(--apple-red) / <alpha-value>)',
        },
      },
      borderRadius: {
        'apple': '12px',
        'apple-sm': '8px',
        'apple-lg': '16px',
      },
      boxShadow: {
        'apple-subtle': 'var(--apple-shadow-subtle)',
        'apple-card': 'var(--apple-shadow-card)',
        'apple-modal': 'var(--apple-shadow-modal)',
      },
    },
  },
  plugins: [],
}
