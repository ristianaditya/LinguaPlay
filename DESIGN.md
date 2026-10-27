# LinguaPlay desktop 0.6

## Direction
A player opens LinguaPlay beside a game in a dim room and wants to select a title and play, not configure a translation service. Follow the supplied WeMod/Wand references: leading library/sidebar, game artwork, compact grouped controls, and a strong Play action.

## Palette
Canvas #101112, sidebar #151617, raised #202224, border #313436, text #f4f5f3, secondary #a8adaa, accent #d6fb51. Accent is restricted to selected navigation and primary actions.

## Type and spacing
Segoe UI, 13px body, 12px metadata, 20px section, 30px game title. Sidebar 216px. Workspace margin 28px, 20px between groups, 40px buttons, 10-14px corner radius. Layout is left aligned.

## Structure
Sidebar / workspace. Library contains a compact feature header, search and status filters, cover collection or real empty state. Game detail contains artwork header and Play, original/translated selection, patch state, file preparation and OCR controls. Existing advanced patch/OCR/backup/service tools remain reachable in sidebar.

## Interaction
Selection opens game detail. Changing play mode never writes files until Play. Show patch mutations explicitly and refuse when game is running or checksums conflict. Local covers and Steam artwork only; no automatic web requests for art.
