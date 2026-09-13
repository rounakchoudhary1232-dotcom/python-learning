import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: { colors: { ink: "#090b10", panel: "#10141c", cyan: "#57d8ff" }, boxShadow: { glow: "0 0 30px rgba(87,216,255,.12)" } } },
  plugins: []
} satisfies Config;
