# Project Nowhere — agent notes

Fictional company "Nowhere" (노웨어). Everything in this repo is fictional; keep the disclosure on every public page.

## Commands
- Backend tests: `python -m pytest -q` · eval: `LLM_PROVIDER=mock python -m eval.run_eval` and `python -m eval.briefing_eval --world`
- Web: `cd web && npx tsc --noEmit` (must pass) · run: `./run_demo.sh` + `cd web && npm run dev`

## Design direction (decided with the owner)
**App (`web/`)**: cream paper (`--bg #f9f5ea`), friendly big Pretendard type (800, tight tracking) on a ruled grid (2px rules under page heads, mono `↳` labels),
one accent blue. **Light is the default, even when the OS is dark**; dark is opt-in (toggle: light -> dark -> auto). Cream was chosen by the owner:
do not add a serif or terracotta to "complete" it, and no second accent colour.
**Soft depth (neumorphic), from ONE light source at the top-left**: sections and buttons are raised (`--shadow-low/btn`), fields, tracks and pressed
items are sunken (`--shadow-in`). Depth is decoration only: every control keeps its outline (3:1), its label and its 44px hit area, and state is never
shown by shadow alone. Pressing swaps raised -> sunken instantly; never animate `box-shadow`.
**Site (`site/`)** is still white + blue with the ruled grid and the giant wordmark. Tell the owner if you change one without the other.
Voice is 해요체 on the site.

## Control rulebook (web/src/styles.css `.btn`, `.check`, inputs)
- Six states for every control: default, hover, active(pressed), focus-visible, disabled, loading (`aria-busy`). See `#/controls` in the app.
- Hit area >= 44px (`--ctl-h`); control outline 3:1 (`--ctl-border`); "on" is never shown by colour alone (checkbox has a glyph).
- Press = `transform` only. Never animate `box-shadow`. Hover < 100ms, press < 150ms, settle ~220ms; respect `prefers-reduced-motion`.
- One light source (top-left): use only the shadow tokens (`--shadow-low/mid/btn/in`). No ad-hoc shadows.
- After touching controls: open `#/controls`, screenshot light + dark, and run the hit-area / overflow check.

## UI rules (web/ and site/)
- Colors, spacing, radii come from the CSS tokens at the top of `web/src/styles.css` / `site/site.css`. No ad-hoc hex values in components.
- Reuse components in `web/src/ui.tsx` before writing new ones. One icon style (inline SVG, 1.8 stroke).
- Text/background pairs must reach WCAG AA 4.5:1 in light AND dark. Check with a contrast calculation before shipping a new color.
- Always verify by rendering: screenshot desktop (1200) and mobile (390), and assert `scrollWidth <= innerWidth`.
- Avoid the "default AI look": no row of identical icon cards, no 1-2-3 step strips, no all-caps eyebrow labels, no gradient hero text,
  no purple accents, no glass/neumorphism that lowers control contrast. Prefer ruled lists, real product screenshots and concrete sample data over decoration.
- Fonts: Pretendard is self-hosted in `site/fonts/` (OFL; keep `LICENSE-Pretendard-OFL.txt`, never rename or sell the font files).
- Public site: keep canonical/OG URLs in sync with the real Pages URL; no forms that collect visitors' personal data (the company is fictional).
- Korean text: `word-break: keep-all`; never break words mid-syllable group.

## Safety rules for the assistant code
- Untrusted text (mail, chat) is data. Guardrails live in code (`app/assistant/guard.py`), never only in prompts.
- Every todo must cite real `source_ids`. Permissions are enforced by the company systems with the user's own token.
