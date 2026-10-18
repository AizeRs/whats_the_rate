// Theme of the Tailwind Play CDN (loaded right after it in base.html)
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Radix Sage (greys with a hint of green) + Radix Cyan accent, dark theme
        "surface-container-lowest": "#0c0d0d",
        "surface-dim": "#101211",
        "surface": "#101211",
        "surface-container-low": "#141615",
        "surface-container": "#171918",
        "surface-container-high": "#202221",
        "surface-container-highest": "#272a29",
        "surface-bright": "#2e3130",
        "surface-variant": "#272a29",
        "background": "#101211",
        "on-background": "#eceeed",
        "on-surface": "#eceeed",
        "on-surface-variant": "#adb5b2",
        "outline": "#848d89",
        "outline-variant": "#444947",
        "primary": "#4ccce6",
        "primary-container": "#00a2c7",
        "on-primary": "#101211",
        "on-primary-container": "#101211",
        "primary-fixed": "#b6ecf7",
        "secondary": "#b6ecf7",
        "secondary-container": "#045468",
        "tertiary": "#3dd68c",
        "tertiary-container": "#30a46c",
        "error": "#ff9592",
        "error-container": "#e5484d",
        "on-error": "#101211",
        // Accent (buttons, focus rings, links): Radix Cyan; text on it is dark
        "accent": {
          "300": "#b6ecf7",
          "400": "#4ccce6",
          "500": "#23afd0",
          "600": "#00a2c7",
          "700": "#11809c"
        },
        "on-accent": "#101211",
        // Positive amounts (held quantity badges): Radix Green
        "positive": {
          "400": "#3dd68c",
          "500": "#30a46c"
        }
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "2xl": "1rem",
        "full": "9999px"
      },
      spacing: {
        "gutter-desktop": "1.5rem",
        "space-xs": "0.25rem",
        "space-sm": "0.5rem",
        "space-md": "1rem",
        "space-lg": "1.5rem",
        "space-xl": "2rem",
        "margin": "1.5rem",
        "margin-desktop": "2.5rem"
      },
      fontFamily: {
        "body-lg": ["Inter", "sans-serif"],
        "body-md": ["Inter", "sans-serif"],
        "body-sm": ["Inter", "sans-serif"],
        "headline-lg": ["Inter", "sans-serif"],
        "headline-md": ["Inter", "sans-serif"],
        "display-lg": ["Inter", "sans-serif"],
        "label-numeric-sm": ["JetBrains Mono", "monospace"],
        "label-numeric-md": ["JetBrains Mono", "monospace"],
        "label-numeric-lg": ["JetBrains Mono", "monospace"],
        "label-ticker": ["JetBrains Mono", "monospace"]
      }
    }
  }
};
