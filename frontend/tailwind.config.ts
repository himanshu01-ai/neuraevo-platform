import type { Config } from "tailwindcss";

/**
 * Tailwind maps the CSS-variable theme contract (styles/globals.css) onto
 * utility classes. Colors are declared as `hsl(var(--token))` so a single
 * `.dark` class switch re-themes the entire app with no JS. Non-color scales
 * mirror design-system/tokens.
 */
const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "./layouts/**/*.{ts,tsx}",
    "./providers/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: { DEFAULT: "1rem", lg: "2rem" },
      screens: { "2xl": "1152px" },
    },
    screens: {
      sm: "640px",
      md: "768px",
      lg: "1024px",
      xl: "1280px",
      "2xl": "1536px",
      "3xl": "1920px",
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1.3" }],
        sm: ["0.8125rem", { lineHeight: "1.4" }],
        base: ["0.875rem", { lineHeight: "1.5" }],
        md: ["1rem", { lineHeight: "1.5" }],
        lg: ["1.125rem", { lineHeight: "1.4" }],
        xl: ["1.375rem", { lineHeight: "1.3" }],
        "2xl": ["1.75rem", { lineHeight: "1.25" }],
        "3xl": ["2.25rem", { lineHeight: "1.2" }],
        "4xl": ["3rem", { lineHeight: "1.1" }],
        "5xl": ["3.75rem", { lineHeight: "1.05" }],
      },
      borderRadius: {
        xs: "0.25rem",
        sm: "calc(var(--radius) - 4px)",
        md: "var(--radius)",
        lg: "calc(var(--radius) + 4px)",
        xl: "calc(var(--radius) + 12px)",
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgb(16 17 22 / 0.04)",
        sm: "0 1px 3px 0 rgb(16 17 22 / 0.06), 0 1px 2px -1px rgb(16 17 22 / 0.06)",
        md: "0 4px 12px -2px rgb(16 17 22 / 0.08), 0 2px 6px -2px rgb(16 17 22 / 0.06)",
        lg: "0 12px 28px -6px rgb(16 17 22 / 0.12), 0 4px 10px -4px rgb(16 17 22 / 0.08)",
        xl: "0 24px 56px -12px rgb(16 17 22 / 0.22), 0 8px 20px -8px rgb(16 17 22 / 0.12)",
        glow: "0 0 0 1px rgb(108 92 242 / 0.30), 0 8px 32px -8px rgb(108 92 242 / 0.35)",
      },
      zIndex: {
        sidebar: "100",
        header: "200",
        dropdown: "1000",
        sticky: "1100",
        overlay: "1200",
        modal: "1300",
        popover: "1400",
        command: "1500",
        toast: "1600",
        tooltip: "1700",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-glow": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms cubic-bezier(0.16,1,0.3,1)",
        "fade-up": "fade-up 320ms cubic-bezier(0.16,1,0.3,1)",
        "accordion-down": "accordion-down 200ms ease-out",
        "accordion-up": "accordion-up 200ms ease-out",
        shimmer: "shimmer 1.6s infinite",
        "pulse-glow": "pulse-glow 4s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
