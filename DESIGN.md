---
name: Lumina Health Intelligence
colors:
  surface: '#f7f9fd'
  surface-dim: '#d8dade'
  surface-bright: '#f7f9fd'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f8'
  surface-container: '#eceef2'
  surface-container-high: '#e6e8ec'
  surface-container-highest: '#e0e2e6'
  on-surface: '#191c1f'
  on-surface-variant: '#454935'
  inverse-surface: '#2d3134'
  inverse-on-surface: '#eff1f5'
  outline: '#757963'
  outline-variant: '#c5c9af'
  surface-tint: '#526600'
  primary: '#526600'
  on-primary: '#ffffff'
  primary-container: '#d2f84b'
  on-primary-container: '#5b7000'
  inverse-primary: '#b0d426'
  secondary: '#5d588f'
  on-secondary: '#ffffff'
  secondary-container: '#c6c0ff'
  on-secondary-container: '#514c83'
  tertiary: '#5e5e62'
  on-tertiary: '#ffffff'
  tertiary-container: '#eae8ec'
  on-tertiary-container: '#68686c'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ccf145'
  primary-fixed-dim: '#b0d426'
  on-primary-fixed: '#171e00'
  on-primary-fixed-variant: '#3d4c00'
  secondary-fixed: '#e4dfff'
  secondary-fixed-dim: '#c6c0ff'
  on-secondary-fixed: '#191348'
  on-secondary-fixed-variant: '#454076'
  tertiary-fixed: '#e3e2e6'
  tertiary-fixed-dim: '#c7c6ca'
  on-tertiary-fixed: '#1a1b1e'
  on-tertiary-fixed-variant: '#46464a'
  background: '#f7f9fd'
  on-background: '#191c1f'
  surface-variant: '#e0e2e6'
typography:
  display-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.025em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  metric-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.03em
  metric-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.025em
  metric-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system embodies a modern, clinical-grade health analytics interface infused with tactile, approachable consumer luxury. It balances medical credibility and precision with the vitality, optimism, and soft physical touch of modern wellness technology.

The aesthetic blends **Modern Minimalist Surface Tiers** with **High-Tactile Neo-Organic Shapes**:
- Deep obsidian and charcoal structural architecture paired with soft, cool-tinted daylight canvases.
- Generous, organic rounded curves (pill geometries and smooth 24px cards) that soften rigid clinical data.
- High-contrast visual accents: electric chartreuse/lime that signals energy and vitality, paired with calming lavender/periwinkle that evokes rest, recovery, and balance.
- Tactile floating elements, hyper-clean progress indicators, and matte contrast cards (such as the deep charcoal nighttime/sleep container) that segment biological chronotypes effortlessly.

## Colors

The palette establishes an asymmetrical duality between deep clinical dark surfaces and ultra-clean, breathable off-white canvas spaces.

### Primary Role (`#d2f84b` - Kinetic Chartreuse)
Used as an electric focal point: status highlights, positive biometric spikes, active tracking meters, primary callout cards, and high-priority action badges.

### Secondary Role (`#b6b0ee` - Restorative Periwinkle/Lavender)
Serves as the harmonic balance to the lime: sleep cycles, secondary metrics, stacked bar segments, and calm state signifiers.

### Tertiary Role (`#18191c` - Deep Obsidian Slate)
The structural anchor: used for the unified lateral control panel, inverted nighttime cards (e.g. sleep/circadian analysis), high-contrast active pills, primary buttons, and metric focal bubbles.

### Neutral Canvas & Surfaces (`#eceef2` to `#ffffff`)
- **App Canvas:** `#eceef2` – a calibrated, soft off-white backdrop that prevents eye strain compared to harsh `#ffffff`.
- **Card Surfaces:** `#ffffff` – clean, pure white floating containers with crisp micro-contrast.
- **Dark Inverted Card:** `#18191c` – dedicated dark mode nested containers for recovery and resting analytics.
- **Text & Hierarchy:** `#18191c` for primary metric values and display titles; `#71747e` for sub-labels and units; `#9a9ea7` for tertiary timestamps and ghost guides.

## Typography

The typography uses **Plus Jakarta Sans** across all hierarchies. Its wide aperture, geometric clarity, and humanist curves reinforce both technical exactness and approachable vitality.

### Rules & Styling Principles
- **Biometric Metric Grouping:** Metric values (e.g., `4,3k`, `62 bpm`) combine bold tabular numerals with lighter or smaller unit descriptors (`body-sm` or `label-sm`) aligned to the baseline or stacked closely.
- **Micro-Badges & Tags:** Positive delta metrics (`+5%`, `+10%`) use `label-sm` set in bold, centered within high-contrast pill capsules.
- **Section Headers:** Display headings feature tight negative tracking (`-0.025em`) to maintain editorial punch without compromising readability.

## Layout & Spacing

The layout is built on an **Asymmetric Split Application Grid**:
- **Navigation Shell:** Fixed-width vertical pillar (260px on desktop) anchored in deep slate `#18191c`, housing the brand mark, navigation pills, notification indicators, and actionable promotional anchors.
- **Main Operational Canvas:** Fluid multi-column workspace wrapped in soft off-white `#eceef2` with an internal margin of `2rem` on desktop.

### Grid & Composition
- **Desktop (1024px+):** 12-column responsive layout with `1.5rem` gutters. Metric cards span 4 columns (or 3-card equal tier), with primary analytics splitting into 6-column or 7/5-column modular dashboards.
- **Tablet (768px – 1023px):** 8-column layout. Sidebar collapses into an icon rail (72px) or top drawer; metric cards span 4 columns each.
- **Mobile (<768px):** Single-column stacked vertical layout. Gutters and canvas margins step down to `1rem`. Sidebar becomes a floating bottom bar or slide-over drawer.

## Elevation & Depth

Visual hierarchy is achieved through **Tonal Surface Stacking and Micro-Borders** rather than heavy blurred drop shadows:

1. **Canvas Base (Level 0):** `#eceef2` provides a matte, low-glare backdrop.
2. **Elevated Card Surface (Level 1):** `#ffffff` panels with continuous 24px corner rounding. Floating separation is defined by an ultra-subtle perimeter stroke: `1px solid rgba(0, 0, 0, 0.03)` with an ambient shadow of `0 8px 24px -4px rgba(24, 25, 28, 0.04)`.
3. **Contrast Surface (Night/Circadian Tier):** Inverted `#18191c` container for sleep and restorative tracking. Rests at the same physical plane but draws high cognitive focus through tone inversion. Internal elements on this tier use subtle semi-transparent white boundaries (`rgba(255, 255, 255, 0.08)`).
4. **Interactive Overlays & Floating Chips (Level 2):** Top search inputs and floating control pills use crisp white fills with `0 4px 12px rgba(0, 0, 0, 0.05)`.
5. **Chart & Bubble Depth:** Intersecting visual gauges (such as energy distribution bubbles) rely on pure color overlap and flat transparency, avoiding skeuomorphic gradients to maintain a clean editorial feel.

## Shapes

The design system embraces an ultra-rounded, organic geometry (Level 3 - Pill & Neo-Curvature):
- **Cards & Primary Modules:** 24px border radius (`rounded-3xl` / `1.5rem`), giving large structural containers an approachable, pebble-like contour.
- **Interactive Controls:** Absolute pill geometry (`9999px` radius) applied to search inputs, navigation state pills, filter dropdowns, buttons, and status chips.
- **Data Visualizations:** Rounded caps on all horizontal and vertical progress bars. Bar charts feature rounded terminal ends, and scatter/matrix dots use perfect circles (`border-radius: 50%`).
- **Bubbles and Metric Clustered Gauges:** Fully circular overlapping discs that communicate volumetric data with soft, organic weight.

## Components

### Buttons & Navigation Pills
- **Active Navigation Pill:** Pure white `#ffffff` fill on dark sidebar, with black icon and high-contrast text (`#18191c`), flanked by an energizing chartreuse pill counter badge (`#d2f84b`).
- **Primary CTA Button:** Dark obsidian pill (`#18191c`) with white text and a rounded-full contour. Inside promotional cards or dark modules, buttons adopt full `#d2f84b` lime fills with `#18191c` bold typography.
- **Secondary / Filter Pills:** Translucent or white pill containers (`padding: 8px 16px`) with integrated trailing chevrons and subdued text.

### Badges & Notification Counters
- **Metric Delta Badges:** Pill-shaped chips (`#d2f84b` background with dark text) nested adjacent to metric values, indicating percentage increases (`+5%`, `+10%`).
- **Numeric Badges:** Circular or pill badges featuring `#d2f84b` with bold 11px numbers for unread alerts.

### Progress Bars & Gauges
- **Horizontal Multi-Metric Trackers:** Wide tracks with generous 12px pill height. Unfilled state is soft gray (`#e5e7eb` or `#2a2b30` on dark containers). Filled tracks use solid segments of lavender (`#b6b0ee`), chartreuse (`#d2f84b`), or deep charcoal (`#18191c`).
- **Circadian Bar Columns:** Vertical comparative bar charts with dual-tone rounded caps. Past days render in muted diagonal hatched patterns or low-opacity fills; the current/selected cycle illuminates in solid `#d2f84b` paired with `#b6b0ee`.

### Biometric Dot Matrix Grid
- Multi-column dot density charts (e.g. Wellness Index) rendered with circular markers (10px diameter, 4px vertical gap). Active levels transition from `#b6b0ee` (lavender) down to low-opacity lavender tints for inactive baselines.

### Input Fields & Search
- **Global Header Search:** Full pill shape (`height: 44px`), white background, subtle border, left-aligned magnifying lens icon with placeholder text in `#9a9ea7`.

### Cards & Tile Hierarchy
- **Standard Clinical Card:** White surface, 24px rounded corners, header with icon, title, and three-dot contextual trigger. Metric showcased in `metric-xl` typography.
- **Sleep & Rest Dark Tile:** Seamless `#18191c` background, white title, sub-metric callouts with vertical indicator bars (e.g. chartreuse bar alongside Sleep Efficiency), followed by the sleep cycle bar chart.
- **Upgrade / Focus Card:** Bright lime card (`#d2f84b`) inside the sidebar with dark typography and an illustrative floating visual element.