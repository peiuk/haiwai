# Official Channel Post Feed Implementation Plan

> **For agentic workers:** Native inline execution. This is a throwaway HTML prototype for visual review.

**Goal:** Improve the post layout after opening an official channel and produce visual screenshots.

**Architecture:** Update the existing channel detail renderer and its local styles in `prototype-x-style.html`. Reuse the current item data, linkification, media/embed renderers, design tokens, and interaction conventions.

**Tech Stack:** Static HTML, CSS, inline JavaScript, existing Playwright CLI.

**Spec:** `docs/superpowers/specs/2026-11-10-official-channel-post-feed-design.md`

## Global Constraints

- Do not change feed ranking, subscriptions, jurisdiction controls, or moderation behavior.
- Keep third-party embeds static until the user clicks to load them.
- Do not add source/license rows to the channel post UI.
- Reuse existing design tokens; no external dependencies.
- Keep touch targets at least 44px.

## Review Focus

- Mobile viewport: channel header and card actions must not overflow.
- Media posts: reuse existing media and embed consent behavior.
- Empty channel: retain a clear empty state.
- Content text: escape and linkify through existing safe helpers.
- Official channel badge and join state must remain visible.

### Task 1: Official channel post layout

**Files:**
- Modify: `prototype-x-style.html`
- Test: `design-system/check-ui.js`

- [x] Add channel post timeline styles.
- [x] Render mixed compact text/media cards without visible source or license details.
- [x] Open channel detail in desktop and 420px mobile viewport and capture screenshots.
- [x] Run `node design-system/check-ui.js`.
