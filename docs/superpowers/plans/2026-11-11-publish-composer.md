# Publish Composer Implementation Plan

> The classified posting flow in this earlier plan was superseded by `docs/superpowers/specs/2026-11-12-classified-composer-design.md` and its implementation plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the existing publish page into an X-style focused editor and unify channel dynamics with optional classified listings.

**Architecture:** Keep the standalone `publish-content.html` and existing publish, draft, authentication, and destination logic. Add an opt-in classified flag to structured info posts while keeping one channel destination. In `prototype-x-style.html`, merge classified cards into the channel dynamic feed and provide an in-feed classified filter, excluding the duplicate standalone listing presentation.

**Tech Stack:** Single-file HTML, CSS, and vanilla JavaScript; existing UKCN shared storage and demo behavior.

**Spec:** `docs/superpowers/specs/2026-11-11-publish-composer-design.md`

## Global Constraints

- Keep the current profile, room, and channel destinations.
- Preserve draft autosave, guest registration, moderation, media validation, AI tags, and post submission behavior.
- A structured listing remains a channel post and appears once in channel dynamics; its classified attribute only controls the in-feed filter.
- Restore draft destination, type, and topics consistently; local media files must be reselected after reload, while failed submissions retain current-page attachments.
- Type-specific validation must remain clear and actionable after the type controls move.
- Do not require channel follows before posting.
- Do not edit the inlined UKCN shared layer or add dependencies.
- Preserve the existing mobile and desktop responsive behavior.

## Review Focus

- Direct entry from a channel keeps the channel destination selected.
- Direct entry from a room keeps the room destination selected.
- Existing drafts restore their selected type, destination, text, and tags after reload, with a clear note that browser-local media files need to be selected again.
- A guest who submits still resumes the publish action after registration.
- Video, topic, and information validation remains active when type controls move into the picker.

---

### Task 1: Refine the existing publish composer

**Files:**
- Modify: `publish-content.html`
- Modify: `prototype-x-style.html`
- Reference: `docs/superpowers/specs/2026-11-11-publish-composer-design.md`

**Interfaces:**
- Preserve existing DOM IDs consumed by the publish and draft logic, including `body`, `destSelect`, `publishBtn`, `typeTabs`, `fileInput`, `videoInput`, and `topicList`, unless an updated consumer is changed in the same task.
- Preserve the existing `setType`, `publish`, `renderDest`, and draft serialization behavior.

- [ ] Move the submit button into the sticky top bar; retain `publishBtn` behavior for disabled, loading, and submission states.
- [ ] Put the body first, then media and type-specific fields, an on-demand content-type picker, and the destination selector. Selecting video, topic, or information must expose and focus its next required action.
- [ ] Remove ambiguous duplicate controls while keeping image, video, topic, and information actions discoverable from the toolbar/picker.
- [ ] Update destination guidance immediately for profile, room, and channel targets; preserve a channel or room target passed in the URL.
- [ ] In info mode, add an opt-in “同时列入分类信息” control for supported channel categories; show structured fields only when selected, keep the destination as the channel, and save/restore the toggle with drafts.
- [ ] Build one channel dynamic feed containing ordinary posts, room pushes, and classified cards; add “全部动态 / 分类信息” filtering, remove the duplicate classified section from channel detail, and keep the separate discovery listing section unchanged.
- [ ] Filter structured listing posts out of the ordinary channel-post projection so each classified post renders once in the channel feed.
- [ ] Keep existing city-topic visibility and removal controls visible before submission.
- [ ] Make validation errors specific to the active type and place them next to the field or action that needs attention.
- [ ] Confirm autosave and restoration keep text, type, destination, and topics; explain that local files need to be reselected after reload and confirm a failed submission keeps current-page attachments retryable.
- [ ] Inspect the final diff and manually review the page at mobile and desktop widths, including profile, room, and channel targets and each content type; do not add or run automated tests unless requested.
