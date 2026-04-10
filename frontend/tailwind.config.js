/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0B1220",
        panel: "#111B2E",
        panelSoft: "#16243D",
        edge: "#273A57",
        accent: "#22D3EE",
        accentSoft: "#1CA5BD",
        danger: "#F43F5E",
        warning: "#F59E0B",
        success: "#10B981",
        textMain: "#E7EEF8",
        textMuted: "#9FB0CC",
      },
      boxShadow: {
        panel: "0 18px 45px rgba(0, 0, 0, 0.38)",
      },
      backgroundImage: {
        "hero-glow":
          "radial-gradient(circle at 20% 20%, rgba(34, 211, 238, 0.18), transparent 35%), radial-gradient(circle at 80% 0%, rgba(59, 130, 246, 0.16), transparent 30%)",
      },
    },
  },
  plugins: [],
};
