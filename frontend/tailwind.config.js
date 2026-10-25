/** @type {import('tailwindcss').Config} */
export default {
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
      colors: {
        apple: {
          bg: "#121214",           // Deep dark charcoal background
          card: "#1c1c1e",         // macOS window/card surface
          subtle: "#242426",       // Inner sub-containers
          subtleHover: "#2c2c2e",  // Interactive hover
          border: "#2c2c2e",       // Subtle border
          borderStrong: "#38383a", // Emphasized border
          text: "#f5f5f7",         // Soft white
          secondary: "#8e8e93",    // Apple system gray
          blue: "#0a84ff",         // Apple Dark System Blue
          blueHover: "#409cff",
          green: "#30d158",        // Apple Dark System Green
          orange: "#ff9f0a",       // Apple Dark System Orange
          red: "#ff453a",          // Apple Dark System Red
        },
      },
      borderRadius: {
        'apple': '12px',
        'apple-sm': '8px',
        'apple-lg': '16px',
      },
      boxShadow: {
        'apple-subtle': '0 1px 3px rgba(0, 0, 0, 0.3)',
        'apple-card': '0 4px 12px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.2)',
        'apple-modal': '0 24px 48px rgba(0, 0, 0, 0.6), 0 0 1px rgba(255, 255, 255, 0.1)',
      },
    },
  },
  plugins: [],
}
