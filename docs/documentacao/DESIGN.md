---
name: Voz Cidadã
colors:
  surface: '#f9f9fc'
  surface-dim: '#dadadc'
  surface-bright: '#f9f9fc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f6'
  surface-container: '#eeeef0'
  surface-container-high: '#e8e8ea'
  surface-container-highest: '#e2e2e5'
  on-surface: '#1a1c1e'
  on-surface-variant: '#494832'
  inverse-surface: '#2f3133'
  inverse-on-surface: '#f0f0f3'
  outline: '#7b7860'
  outline-variant: '#cbc7ab'
  surface-tint: '#656100'
  primary: '#656100'
  on-primary: '#ffffff'
  primary-container: '#ebe100'
  on-primary-container: '#676300'
  inverse-primary: '#d4cb00'
  secondary: '#006d30'
  on-secondary: '#ffffff'
  secondary-container: '#92f5a4'
  on-secondary-container: '#007233'
  tertiary: '#006398'
  on-tertiary: '#ffffff'
  tertiary-container: '#c1e0ff'
  on-tertiary-container: '#00669b'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#f2e813'
  primary-fixed-dim: '#d4cb00'
  on-primary-fixed: '#1e1c00'
  on-primary-fixed-variant: '#4c4800'
  secondary-fixed: '#95f8a7'
  secondary-fixed-dim: '#79db8d'
  on-secondary-fixed: '#00210a'
  on-secondary-fixed-variant: '#005323'
  tertiary-fixed: '#cce5ff'
  tertiary-fixed-dim: '#93ccff'
  on-tertiary-fixed: '#001d31'
  on-tertiary-fixed-variant: '#004b73'
  background: '#f9f9fc'
  on-background: '#1a1c1e'
  surface-variant: '#e2e2e5'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  title-lg:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  title-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.06em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-tablet: 1.5rem
  gutter-desktop: 2rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system powers a civic engagement and urban stewardship platform dedicated to active citizenship, reporting public infrastructure issues, and fostering municipal transparency. 

The brand persona is vigilant, constructive, civic-minded, and empowering. It balances the urgency of civic reporting with the steady, institutional authority required for municipal resolution. Visual styling borrows from **Modern Functionalism** and **Tactile Utility**—drawing inspiration from international civic signage, urban wayfinding, and clean municipal dashboards. High-contrast typography and vivid civic status indicators convey clarity and accountability, ensuring that any citizen, regardless of technical literacy or device capability, can file a report, track a potholes repair, or monitor public works in their neighborhood.

## Colors

The palette is engineered around high functional contrast and municipal recognition:

- **Primary Yellow (`#ebe100`)**: An alert, civic-caution yellow used for primary badges, prominent alerts, key callout surfaces, and focal indicators. It represents civic attention and illumination. Whenever text or icons sit on the primary yellow surface, they must strictly use the dark charcoal neutral (`#1a1c1e`) to guarantee WCAG AAA legibility.
- **Secondary Emerald (`#15803d`)**: A grounded civic green embodying urban renewal, resolution, sustainability, and action. Applied to primary action triggers, "New Report" buttons, resolved tickets, and confirmation states.
- **Tertiary Civic Blue (`#0284c7`)**: Used for municipal routing, status updates (in-progress), and institutional verification tags.
- **Neutral Dark Charcoal (`#1a1c1e`)**: Grounding body text, primary icons, and structural frames, avoiding the harshness of pure black while providing crisp legibility.
- **Canvas & Containers**: Clean off-white baseline surfaces (`#f8fafc`) layered with pure white (`#ffffff`) for elevated cards, framed by subtle slate outlines (`#e2e8f0`).

## Typography

The typographic hierarchy conveys municipal rigor alongside open public utility:

- **Headlines (Space Grotesk)**: Provides an authoritative, civic, and structured appearance reminiscent of street signage and technical documentation. Its geometric balance ensures strong presence at large scales.
- **Body & Content (Hanken Grotesk)**: Offers crisp, neutral, modern readability across high-density incident descriptions, comments, and protocol feeds.
- **Labels & System Meta (JetBrains Mono)**: Protocol IDs, geo-coordinates, timestamps, priority tags, and status trackers adopt a monospaced format to underline technical precision, official tracking, and auditability.

## Layout & Spacing

The layout is built on a responsive 12-column fluid grid system that prioritizes situational reporting on mobile devices and analytical density on desktop monitors:

- **Mobile (< 768px)**: 4 columns, `margin: 1rem`, `gutter: 1rem`. Focuses on quick incident logging, photo uploads, and map-centric bottom sheets.
- **Tablet (768px - 1024px)**: 8 columns, `margin: 2rem`, `gutter: 1.5rem`. Split views displaying incident lists alongside interactive zoning maps.
- **Desktop (> 1024px)**: 12 columns, `margin: 3rem`, `gutter: 2rem`, capped at a max-width of `1440px`. Dedicated to administrative triage, municipal analytics, heatmaps, and citizen resolution portals.

Vertical spacing relies strictly on multiples of `0.25rem` (`4px`), anchoring micro-padding at `0.5rem` (`space-sm`) and card gutters at `1.5rem` (`space-lg`).

## Elevation & Depth

Visual depth is achieved through **low-contrast structural outlines combined with ambient, tinted micro-shadows**. This avoids visual clutter under bright outdoor mobile usage:

- **Level 0 (Flat/Base)**: `#f8fafc` canvas background with zero shadow.
- **Level 1 (Card/Container)**: Pure white `#ffffff` surface, bounded by a 1px border (`#e2e8f0`), paired with a soft ambient drop shadow: `0px 1px 3px rgba(26, 28, 30, 0.05)`.
- **Level 2 (Active/Interactive)**: Used for hover states, floating actions, and filter sheets: `0px 4px 12px rgba(26, 28, 30, 0.08)`, 1px border (`#cbd5e1`).
- **Level 3 (Modals/Bottom Drawers)**: High-priority dialogue modals and report flow overlays: `0px 12px 32px rgba(26, 28, 30, 0.16)`.
- **Accented Focus**: When an element is selected or in active focus, depth is signaled via a crisp `2px` offset ring using `#ebe100` backed by `#15803d` inner focus.

## Shapes

The design system employs **Rounded Level 2** (`rounded: 0.5rem`, `rounded-lg: 1rem`, `rounded-xl: 1.5rem`).

This curvature provides an approachable, modern community feel without losing the structural discipline of municipal management tools:
- **Buttons, inputs, and chips**: `0.5rem` (`rounded`) for ergonomic touch targets.
- **Cards, alert banners, and image containers**: `1rem` (`rounded-lg`) for smooth sectional division.
- **Bottom sheets, persistent navigation, and modal dialogues**: `1.5rem` (`rounded-xl`) on leading corners.
- **Status Pills & Tracking Chips**: Fully pill-shaped (`9999px`) to maintain clear differentiation from informational cards.

## Components

### Buttons
- **Primary Civic Action (Report / Confirm)**: Solid `#15803d` with white `#ffffff` text, font weight 600. On hover: darken to `#166534`.
- **Urgent / Spotlight Action**: Solid `#ebe100` background with `#1a1c1e` text, font weight 700. Used for instant action triggers, verification prompts, and emergency civic warnings.
- **Secondary / Ghost**: White background, 1px border `#cbd5e1`, text `#1a1c1e`.

### Chips & Badges
- **Status Chips**: Monospaced labels (`JetBrains Mono`, `label-md`). 
  - *Em Aberto (Pending)*: `#fef9c3` background, `#854d0e` text, border `#fde047`.
  - *Em Andamento (In Progress)*: `#e0f2fe` background, `#0369a1` text, border `#7dd3fc`.
  - *Resolvido (Resolved)*: `#dcfce7` background, `#15803d` text, border `#86efac`.
- **Category Filter Chips**: Rounded pill shape (`9999px`), 1px outline `#e2e8f0`. Selected state toggles to solid `#1a1c1e` with white text.

### Cards
- Standard report card features white background, `rounded-lg` corners, 1px `#e2e8f0` border, and level 1 shadow. Header displays the protocol ID in monospaced font alongside category badge, followed by title in `Space Grotesk`, location pin, and status pill.

### Input Fields
- Text inputs and textareas use a white container, `0.5rem` radius, 1.5px border `#cbd5e1`. Placeholder text in `#64748b`. Focused state uses a 2px border `#15803d` with an outer `#ebe100` halo ring.

### Checkboxes & Radio Buttons
- Custom controls with `0.25rem` radius (checkbox) or circular (radio), `#1a1c1e` border. When checked, filled with `#15803d` and white vector glyphs.

### Special Civic Components
- **Geotagged Incident Attachment**: Media upload box with dashed border (`#94a3b8`), camera trigger icon, and live GPS coordinate pill (`JetBrains Mono`).
- **Resolution Timeline Meter**: A vertical stepped path connecting citizen submission, municipal triage, agency dispatch, and neighborhood validation with emerald checkmark nodes.