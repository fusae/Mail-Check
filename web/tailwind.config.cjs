/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./index.tsx"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Space Grotesk'", "system-ui", "sans-serif"],
        body: ["'Sora'", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
