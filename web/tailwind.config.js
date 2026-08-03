/** @type {import('tailwindcss').Config} */
const daisyui = require('daisyui')
const typography = require('@tailwindcss/typography')
const themeCatalog = require('./src/config/themeCatalog.json')

const daisyThemes = Object.entries(themeCatalog.themes).map(([name, config]) =>
  config ? { [name]: config } : name
)

module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      screens: {
        'xs': '475px',
        'md-lg': '896px',
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
        'xs-tight': ['0.6875rem', { lineHeight: '1rem' }],
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },
      zIndex: {
        // Base layers
        'base': '0',
        'content': '1',

        // Interactive elements
        'button': '10',
        'input': '20',
        'dropdown': '30',

        // Overlays and modals
        'overlay': '1000',
        'modal': '2000',
        'modal-overlay': '1999',
        'modal-nested': '2100',
        'loading-overlay': '15',

        // Floating elements
        'tooltip': '3000',
        'popover': '3100',
        'notification': '3200',
        'toast': '5000',

        // Fixed positioned elements
        'fab': '4000',
        'header': '4100',
        'sidebar': '4200',

        // Highest priority
        'max': '9999',
      },
      typography: ({ theme }) => ({
        DEFAULT: {
          css: {
            color: theme('colors.base-content'),
            maxWidth: 'none',
            lineHeight: theme('lineHeight.relaxed'),
            a: {
              color: theme('colors.primary'),
              fontWeight: theme('fontWeight.medium'),
              textDecoration: 'none',
              '&:hover': {
                textDecoration: 'underline',
              },
            },
            strong: {
              color: 'inherit',
              fontWeight: theme('fontWeight.semibold'),
            },
            blockquote: {
              color: 'hsl(var(--bc) / 0.85)',
              borderLeftColor: 'hsl(var(--b3) / 0.8)',
              fontStyle: 'italic',
            },
            'ol > li::marker': {
              color: 'inherit',
            },
            'ul > li::marker': {
              color: 'inherit',
            },
            code: {
              color: 'inherit',
              backgroundColor: 'hsl(var(--b3) / 0.35)',
              padding: '0.15em 0.35em',
              borderRadius: theme('borderRadius.lg'),
              fontWeight: theme('fontWeight.medium'),
            },
            pre: {
              color: 'inherit',
              backgroundColor: 'hsl(var(--b3) / 0.25)',
              borderRadius: theme('borderRadius.lg'),
              padding: theme('spacing.4'),
              boxShadow: 'inset 0 0 0 1px hsl(var(--b3) / 0.35)',
            },
            hr: {
              borderColor: 'hsl(var(--b3) / 0.6)',
            },
            table: {
              width: '100%',
            },
          },
        },
        sm: {
          css: {
            fontSize: theme('fontSize.sm')[0],
            lineHeight: theme('fontSize.sm')[1].lineHeight,
            code: {
              fontSize: theme('fontSize.sm')[0],
            },
          },
        },
      }),
    },
  },
  plugins: [daisyui, typography],
  daisyui: {
    styled: true,
    themes: daisyThemes,
    base: true,
    utils: true,
    logs: false,
    prefix: "",
    themeRoot: ":root",
  },
}
