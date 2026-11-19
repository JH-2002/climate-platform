import type { Config } from "tailwindcss";

// Cores de estado sempre acompanhadas de texto e ícone (Constituição §11).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: "#ffffff", muted: "#f5f7f9", border: "#dde3e8" },
        ink: { DEFAULT: "#14202b", muted: "#4d5d6b" },
        accent: { DEFAULT: "#0b5c7a", strong: "#08465d" },
        status: {
          ok: "#1e7a46",
          warn: "#8a5a00",
          error: "#b42318",
          unknown: "#5b6670",
        },
      },
      fontFamily: {
        sans: ["system-ui", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
