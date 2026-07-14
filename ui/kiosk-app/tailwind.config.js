/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F172A",
        muted: "#64748B",
        line: "#E2E8F0",
        canvas: "#F8FAFC",
        brand: {
          50: "#EEF2FF",
          100: "#E0E7FF",
          500: "#6366F1",
          600: "#4F46E5",
          700: "#4338CA",
        },
        indigo: {
          50: "#EEF2FF",
          100: "#E0E7FF",
          500: "#6366F1",
          600: "#4F46E5",
          700: "#4338CA",
        },
        cyan: {
          50: "#ECFEFF",
          100: "#CFFAFE",
          500: "#06B6D4",
          600: "#0891B2",
          700: "#0E7490",
        },
        emerald: {
          50: "#ECFDF3",
          500: "#12B76A",
          700: "#027A48",
        },
        amber: {
          50: "#FFFAEB",
          500: "#F79009",
          700: "#B54708",
        },
        rose: {
          50: "#FFF1F3",
          500: "#F63D68",
          700: "#C01048",
        },
      },
      boxShadow: {
        soft: "0 16px 44px rgba(16, 24, 40, 0.08)",
        card: "0 8px 24px rgba(16, 24, 40, 0.06)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
