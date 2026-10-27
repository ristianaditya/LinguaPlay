# LinguaPlay desktop 0.7

## Direction
A player opens LinguaPlay beside a game in a dim room and wants to select a title and play, not configure a translation service. Follow the supplied WeMod/Wand references: glass panels floating on a dark canvas, leading library rail, poster artwork, grouped rows with an icon on the left and a control on the right, pill buttons and a strong Play action.

## Palette
Canvas #0a0c0c with a faint lime radial glow top-right, rail rgba(14,16,16,.82), glass cards gradient #222627→#181b1c with 7% white border, text #eef1ee, secondary #a3aba6, eyebrow #8a928d, accent #d6fb51. Accent is restricted to selection, primary actions, icons in group headers and progress.

## Type and spacing
Segoe UI, 13px body, 12px metadata, 11px uppercase eyebrow (letter-spacing 1.2px), 16px section, 26px page heading, 32-36px library/game titles. Rail 224px. Workspace margin 30px. Cards 18px radius, inputs 12px, pills fully rounded.

## Icons
Own 24px line icon set in `linguaplay/icons.py`, tinted at runtime (Normal + Disabled). No emoji or font glyph icons; no text symbols that can be mis-encoded.

## Motion
- Page change: fade + 14px rise (280ms, OutCubic); effect removed at rest.
- Navigation highlight slides between rail entries (320ms).
- Busy: spinner beside the status and a travelling shimmer on the 3px activity line.
- Primary/pill buttons glow on hover/focus; status text fades in unless updates are rapid.
- Play mode is a segmented Asli/Terjemahan switch with a sliding knob, bound to the hidden combo.
- QGraphicsEffects are never nested inside cards (Qt renders nested effects incorrectly).

## In-game overlay
Ctrl+Alt+O opens a Steam/Discord-style layer: full-screen dim with vignette, top bar (brand, OCR state, clock, hotkey), last subtitle card, quick action pills (change area, stop OCR, open app, back to game) and the floating glass settings panel. Clicking the backdrop or Esc returns to the game. OCR is paused while it is open. Subtitles carry a dark outline shadow and fade in on change.

## Interaction
Selection opens game detail. Changing play mode never writes files until Play. Show patch mutations explicitly and refuse when game is running or checksums conflict. Local covers and Steam artwork only; no automatic web requests for art.
