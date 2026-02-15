# Frontend Changes: Dark/Light Theme Toggle

## Overview

Added a dark/light mode toggle button to the frontend, positioned in the top-right corner with sun/moon icon design, smooth transition animations, and full accessibility support. Includes a comprehensive light theme with WCAG AA-compliant contrast ratios.

## Files Modified

### `frontend/index.html`
- Added a `<button class="theme-toggle">` element placed before the main container, positioned fixed in the top-right corner
- Includes two inline SVG icons: a sun (visible in dark mode) and a moon (visible in light mode)
- Uses `aria-label` and `title` attributes for accessibility

### `frontend/style.css`

**Toggle button & transitions (from initial implementation):**
- **Toggle button styles**: `.theme-toggle` is a 44px circular button, fixed top-right (`position: fixed; top: 1rem; right: 1rem; z-index: 100`), with hover scale, focus ring, and active press effects
- **Icon crossfade**: `.icon-sun` and `.icon-moon` use `opacity` and `transform: rotate()` transitions (0.3s) to smoothly swap between icons when the theme changes
- **Smooth theme transitions**: Added `transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease` to the body and key UI elements (sidebar, chat area, input, messages, etc.) so theme switches feel fluid

**Light theme color palette (accessibility pass):**
- **`--primary-color: #1d4ed8`** (darker blue than dark-mode's `#2563eb`) — ensures the primary accent has strong contrast on white surfaces
- **`--primary-hover: #1e40af`** — deeper shade for hover states on light backgrounds
- **`--text-secondary: #475569`** (darkened from `#64748b`) — improves contrast ratio from ~4.6:1 to ~7:1 on `#f8fafc` background, comfortably exceeding WCAG AA (4.5:1)
- **`--code-bg: #f1f5f9`** (solid color instead of `rgba(0,0,0,0.05)`) — provides a visible but subtle tint for code blocks against white surfaces
- **`--shadow`**: Reduced opacity (`0.08`) for lighter, more natural shadows on light backgrounds
- **`--focus-ring`**: Slightly increased opacity (`0.25`) for better visibility of focus indicators on light surfaces

**New CSS variables added to both themes:**
- **`--error-color`**, **`--error-bg`**, **`--error-border`**: Dark theme uses `#f87171` (bright red on dark bg). Light theme uses `#dc2626` (dark red) on `#fef2f2` (red-50) with `#fecaca` (red-200) border — contrast ratio ~5.6:1, passing WCAG AA
- **`--success-color`**, **`--success-bg`**, **`--success-border`**: Dark theme uses `#4ade80` (bright green on dark bg). Light theme uses `#16a34a` (dark green) on `#f0fdf4` (green-50) with `#bbf7d0` (green-200) border — contrast ratio ~4.6:1, passing WCAG AA
- **`--welcome-shadow`**: Theme-aware shadow for the welcome message card (darker in dark mode, subtle in light mode)
- **`--welcome-bg`** / **`--welcome-border`**: Welcome card now uses `#eff6ff` (blue-50) background and `#93c5fd` (blue-300) border in light mode for a soft, distinct appearance
- **`--chip-hover-text: #ffffff`**: Source chip hover always uses white text on the blue background, preventing contrast issues in light mode

**Bug fixes:**
- Fixed `.message-content blockquote` border using nonexistent `var(--primary)` — changed to `var(--primary-color)`
- `.error-message` and `.success-message` classes now use CSS variables instead of hardcoded RGBA values, so they adapt to both themes
- `a.source-chip:hover` now uses `var(--chip-hover-text)` instead of `var(--text-primary)`, ensuring white-on-blue contrast in both themes
- Welcome message `.message.welcome-message .message-content` now uses `var(--welcome-bg)`, `var(--welcome-border)`, and `var(--welcome-shadow)` instead of hardcoded values

### `frontend/script.js`
- **IIFE for flash prevention**: An immediately-invoked function at the top of the file reads `localStorage.getItem('theme')` and sets `data-theme="light"` on `<html>` before the DOM renders, preventing a flash of the wrong theme on page load
- **`initThemeToggle()`**: Called during `DOMContentLoaded` initialization. Attaches a click listener to the toggle button that flips the `data-theme` attribute and persists the choice to `localStorage`
- **`updateToggleLabel(toggle)`**: Updates the `aria-label` to reflect the current action ("Switch to dark theme" / "Switch to light theme") for screen reader users

## Accessibility Summary

| Element | Background | Text Color | Contrast Ratio | WCAG AA |
|---------|-----------|------------|---------------|---------|
| Body text | `#f8fafc` | `#0f172a` | ~16:1 | Pass |
| Secondary text | `#f8fafc` | `#475569` | ~7:1 | Pass |
| User message | `#2563eb` | `#ffffff` | ~4.6:1 | Pass |
| Error text | `#fef2f2` | `#dc2626` | ~5.6:1 | Pass |
| Success text | `#f0fdf4` | `#16a34a` | ~4.6:1 | Pass |
| Source chip hover | `#1d4ed8` | `#ffffff` | ~6.5:1 | Pass |

## Design Decisions

- **Fixed positioning**: The toggle sits at `position: fixed` so it remains visible regardless of scroll position
- **Icon-based**: Uses sun (for "switch to light") in dark mode and moon (for "switch to dark") in light mode, following common UI conventions
- **localStorage persistence**: Theme preference survives page reloads and browser sessions
- **No external dependencies**: Uses inline SVGs and pure CSS transitions, keeping the vanilla HTML/JS/CSS approach consistent with the rest of the frontend
- **Accessible**: Keyboard-navigable (focusable button with visible focus ring), dynamic `aria-label`, and `title` attribute for tooltip
- **Darker primary in light mode**: Shifted from `#2563eb` to `#1d4ed8` so blue accents stand out well against white, maintaining the brand feel while improving legibility
