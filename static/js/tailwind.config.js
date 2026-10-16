// Theme of the Tailwind Play CDN (loaded right after it in base.html)
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "surface-container-lowest": "#0a0e17",
        "surface-dim": "#0f131c",
        "surface": "#0f131c",
        "surface-container-low": "#181b25",
        "surface-container": "#1c1f29",
        "surface-container-high": "#262a34",
        "surface-container-highest": "#31353f",
        "surface-bright": "#353943",
        "surface-variant": "#31353f",
        "background": "#0f131c",
        "on-background": "#dfe2ef",
        "on-surface": "#dfe2ef",
        "on-surface-variant": "#c2c6d6",
        "outline": "#8c909f",
        "outline-variant": "#424754",
        "primary": "#adc6ff",
        "primary-container": "#3b82f6",
        "on-primary": "#002e6a",
        "on-primary-container": "#ffffff",
        "primary-fixed": "#d8e2ff",
        "secondary": "#c0c1ff",
        "secondary-container": "#3131c0",
        "tertiary": "#4edea3",
        "tertiary-container": "#00a572",
        "error": "#ffb4ab",
        "error-container": "#93000a",
        "on-error": "#690005"
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
