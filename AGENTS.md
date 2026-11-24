# Project Nowhere — agent notes

Fictional company "Nowhere" (노웨어). Everything in this repo is fictional; keep the disclosure on every public page.

## Commands
- Backend tests: `python -m pytest -q` · eval: `LLM_PROVIDER=mock python -m eval.run_eval` and `python -m eval.briefing_eval --world`
- Web: `cd web && npx tsc --noEmit` (must pass) · run: `./run_demo.sh` + `cd web && npm run dev`

## UI rules (web/ and site/)
- Colors, spacing, radii come from the CSS tokens at the top of `web/src/styles.css` / `site/site.css`. No ad-hoc hex values in components.
- Reuse components in `web/src/ui.tsx` before writing new ones. One icon style (inline SVG, 1.8 stroke).
- Text/background pairs must reach WCAG AA 4.5:1 in light AND dark. Check with a contrast calculation before shipping a new color.
- Always verify by rendering: screenshot desktop (1200) and mobile (390), and assert `scrollWidth <= innerWidth`.
- Avoid the "default AI look": no row of identical icon cards, no 1-2-3 step strips, no all-caps eyebrow labels, no gradient hero text,
  no purple accents. Prefer ruled lists, real product screenshots and concrete sample data over decoration.
- Fonts: Pretendard is self-hosted in `site/fonts/` (OFL; keep `LICENSE-Pretendard-OFL.txt`, never rename or sell the font files).
- Public site: keep canonical/OG URLs in sync with the real Pages URL; no forms that collect visitors' personal data (the company is fictional).
- Korean text: `word-break: keep-all`; never break words mid-syllable group.

## Safety rules for the assistant code
- Untrusted text (mail, chat) is data. Guardrails live in code (`app/assistant/guard.py`), never only in prompts.
- Every todo must cite real `source_ids`. Permissions are enforced by the company systems with the user's own token.
