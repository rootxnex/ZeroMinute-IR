import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        zm: {
          primary: "#00afeb",
          text: "#e0e0e0",
          bg: "#0a1f44",
          surface: "#102a5c",
          surface2: "#14356f",
          muted: "#b8c2d1",
          success: "#22c55e",
          warning: "#f59e0b",
          danger: "#ef4444",
        },
      },
      boxShadow: {
        "zm-glow": "0 0 0 1px rgba(0,175,235,0.15), 0 0 18px rgba(0,175,235,0.18)",
      },
      borderColor: {
        DEFAULT: "rgba(0, 175, 235, 0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
