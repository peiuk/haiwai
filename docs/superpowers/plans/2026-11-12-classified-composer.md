# Classified Composer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make an information post a classified listing with a selected category and category-specific fields.

**Architecture:** Keep `publish-content.html` as the composer and preserve the existing `listing.kind` / `listing.area` data shape consumed by `prototype-x-style.html`. The selected category controls the listing form, and submission is allowed only when the destination is a channel with a matching category.

**Tech Stack:** Single-file HTML, CSS, vanilla JavaScript, existing UKCN storage.

**Spec:** `docs/superpowers/specs/2026-11-12-classified-composer-design.md`

## Global Constraints

- Keep the channel as the only post destination; do not create a separate classified destination.
- Preserve the single channel dynamic feed and its classified filter.
- Store the selected category in post `category`; map 房产 subtypes to `listing.kind` (`rent`, `sale`, `commercial`), 市场 to `secondhand`, 招聘 to `job`, and keep `listing.area` as the single location string.
- Add property subtypes `rent`, `sale`, and `commercial`; replace the job work-permit field with `position`.
- Derive price currency from the destination channel region (`UK` → GBP, `JP` → JPY, `CA` → CAD); use the selected country for global destinations and a generic symbol when unknown.
- Do not add dependencies or change the shared storage layer.
- Do not add or run automated tests unless requested.

## Review Focus

- Category change switches the category-specific fields and retains title and location.
- Channel/category mismatch blocks submission with a clear field-level message.
- Non-channel destinations cannot submit classified listings.
- Successful submission keeps the selected kind and location available to existing listing cards.

---

### Task 1: Make information posts select their listing category

**Files:**
- Modify: `publish-content.html`
- Modify: `prototype-x-style.html`

**Interfaces:**
- Preserve `collectListing()` output: `{ kind, price, unit, area, attrs }`.
- Preserve `listingSpec()` and `listingFormHTML()` category form definitions, adapting them to the selected category instead of only the destination category.

- [x] Replace the optional classified checkbox and inherited category display with a required category selector immediately after the title.
- [x] On category selection, show the matching existing structured fields and retain title and location while rerendering.
- [x] Add one required free-text location field (existing `area` storage key) with a city/area example placeholder.
- [x] Validate category selection, location, price, category-specific fields, and destination/category match; focus the first relevant field on error.
- [x] Submit every `info` post with a structured `listing` whose `kind` follows the selected category mapping, and clear category/location after successful submission.
- [x] Update draft snapshot/restore to include selected category and location, replacing the prior `includeClassified` state.
- [x] Add property subtype forms for rental, sale, and commercial property; use the selected subtype as `listing.kind`.
- [x] Replace the job work-permit field with a required position field and update listing detail metadata.
- [x] Render currency symbols from the destination channel's country on the composer, listing cards, and listing details.
- [x] Review changed code paths and confirm compatibility with existing listing rendering by source inspection; do not run automated tests.
