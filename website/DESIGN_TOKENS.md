# Shakti-Chain design tokens

Source: `shaktichain_ui_ux_audit.md` (September 2026). Implemented on the public site and the demo app.

## Palette

| Token | Hex | Use |
|---|---|---|
| Primary | `#10B981` | Borders, icons, role kicker (EV, DISCOM) |
| Primary dark | `#047857` | Button fill (white text, WCAG AA) |
| Secondary / saffron | `#F59E0B` | Metrics, lightning mark, CPO |
| Teal | `#14B8A6` | Intelligence layer, fleet |
| Warning | `#EA580C` | Coalition metric, aggregator |
| Deep slate | `#1F2937` | Hero, body text on light surfaces |

White text sits on `#047857`, not on `#10B981`, so button contrast stays at least AA. Metric saffron is large type.

## Type

- UI: Inter
- Technical terms (`ERC-20`, kWh): Fira Code

## Motion

Pulse and rise animations honour `prefers-reduced-motion`.

## Files

- Landing: `website/assets/css/design-tokens.css`
- Demo: `v2g-marketplace/frontend/src/styles/tokens.css`

Not in this pass: Figma, Storybook, briefing PDF recolour, commissioned raster illustration.
