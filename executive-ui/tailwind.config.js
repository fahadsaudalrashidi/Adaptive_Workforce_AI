/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        // Phase 11 — deep-navy corporate palette. More blue-saturated than
        // generic Tailwind slate (which reads neutral-gray, not "navy"),
        // used for page background + card elevation levels.
        navy: {
          950: '#080b16',
          900: '#0c1120',
          800: '#111830',
          700: '#182242',
          600: '#212f56',
          500: '#2e3f70',
          400: '#4c5d8a',
          300: '#7788ab',
          200: '#a9b4cc',
          100: '#d7dce8',
        },
        // Phase 11 — restrained premium accent, layered ON TOP of the
        // existing blue functional accent (not a replacement for it — see
        // DESIGN_SYSTEM.md). Reserved for "this is the top tier / the
        // headline finding / the elevated moment" signals: hero card
        // accents, Platinum-tier badges, chart highlight bars.
        gold: {
          50:  '#fdf8ec',
          100: '#faedc4',
          200: '#f3d888',
          300: '#eabf4f',
          400: '#d4af37',
          500: '#b8932c',
          600: '#967322',
          700: '#74581c',
        },
        risk: {
          stable:   '#059669',
          monitor:  '#d97706',
          concern:  '#ea580c',
          priority: '#dc2626',
        },
        surface: {
          DEFAULT: '#1e293b',
          elevated: '#334155',
          deep: '#0f172a',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        arabic: ['Cairo', 'system-ui', 'sans-serif'],
      },
      // Phase 11 — deliberate type scale. Existing raw Tailwind sizes
      // (text-2xl etc.) remain valid and widely used across pre-existing
      // pages; these named sizes are additive, for new/touched components
      // that want an explicit place in the hierarchy.
      fontSize: {
        display:  ['2.75rem', { lineHeight: '1.1', fontWeight: '700', letterSpacing: '-0.02em' }],
        headline: ['1.875rem', { lineHeight: '1.2', fontWeight: '700', letterSpacing: '-0.01em' }],
        title:    ['1.25rem', { lineHeight: '1.35', fontWeight: '600' }],
        body:     ['0.875rem', { lineHeight: '1.55', fontWeight: '400' }],
        caption:  ['0.75rem', { lineHeight: '1.4', fontWeight: '500', letterSpacing: '0.02em' }],
      },
      // Phase 11 — colored (navy-tinted) elevation shadows instead of
      // generic black shadows, which read flat/cheap on a dark background.
      boxShadow: {
        'elevation-1': '0 1px 2px rgba(4, 7, 18, 0.4), 0 1px 3px rgba(8, 15, 35, 0.3)',
        'elevation-2': '0 4px 12px rgba(4, 7, 18, 0.45), 0 2px 4px rgba(8, 15, 35, 0.35)',
        'elevation-3': '0 12px 32px rgba(4, 7, 18, 0.55), 0 4px 10px rgba(8, 15, 35, 0.4)',
        'glow-gold':   '0 0 0 1px rgba(212, 175, 55, 0.4), 0 4px 20px rgba(212, 175, 55, 0.15)',
        'glow-brand':  '0 0 0 1px rgba(59, 130, 246, 0.4), 0 4px 20px rgba(59, 130, 246, 0.15)',
      },
      // Phase 11 — motion tokens: consistent transition feel platform-wide.
      transitionDuration: {
        fast: '150ms',
        base: '250ms',
        slow: '400ms',
      },
      transitionTimingFunction: {
        executive: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer': 'shimmer 1.8s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(16px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-468px 0' },
          '100%': { backgroundPosition: '468px 0' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-executive': 'linear-gradient(135deg, #1e3a8a 0%, #0e7490 100%)',
        'gradient-navy-deep': 'linear-gradient(180deg, #0c1120 0%, #080b16 100%)',
        'gradient-gold-accent': 'linear-gradient(135deg, #d4af37 0%, #967322 100%)',
      },
    },
  },
  plugins: [],
}
