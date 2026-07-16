# SEO Page Generation Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate and safely publish 24 noindex SEO pages for the Minsk — Uzda route from the approved Excel content.

**Architecture:** A dependency-free XLSX reader converts the workbook into typed SEO rows. A pure HTML renderer applies one row to the approved route template. A separate MODX deployment script creates only marker-owned, prefixed resources and writes a public manifest.

**Tech Stack:** Python 3.10+, `zipfile`, `xml.etree.ElementTree`, BeautifulSoup, Requests, unittest, MODX connector API.

---

### Task 1: Import the SEO workbook

**Files:**
- Create: `scripts/seo_generation.py`
- Create: `tests/test_seo_generation.py`

1. Add a failing test that loads the supplied workbook and expects 24 typed rows with all 23 columns mapped.
2. Run `python -m unittest tests.test_seo_generation.SeoWorkbookTests -v` and confirm the import failure.
3. Implement an XLSX reader using standard-library ZIP/XML parsing; do not add `openpyxl`.
4. Re-run the focused test and confirm it passes.

### Task 2: Generate deterministic page HTML

**Files:**
- Modify: `scripts/seo_generation.py`
- Modify: `tests/test_seo_generation.py`

1. Add failing tests for placeholder replacement, Cyrillic slug generation, unique prefixed aliases, metadata, H1, price/private/business copy, FAQ HTML, gallery heading and contact heading.
2. Run the focused generation tests and confirm failure.
3. Implement `GeneratedPage`, placeholder replacement, transliteration, row selection and BeautifulSoup-based rendering from `index.html`.
4. Re-run the focused tests and confirm all pass.

### Task 3: Protect existing MODX resources

**Files:**
- Create: `scripts/deploy_modx_generated.py`
- Modify: `tests/test_seo_generation.py`

1. Add failing tests for the resource ownership marker and rejection of an existing resource without that marker.
2. Run the focused deployment-safety tests and confirm failure.
3. Implement CLI arguments, local dry-run, exact-alias lookup, marker validation, create/update calls, shared asset upload and JSON manifest output.
4. Re-run the focused tests and confirm all pass.

### Task 4: Document and validate the local batch

**Files:**
- Modify: `README.md`

1. Document the dry-run and live commands without credentials.
2. Run a dry-run for Minsk — Uzda and confirm 24 unique aliases, complete placeholders and no mutation.
3. Run `python -m unittest discover -s tests -v`.

### Task 5: Publish and verify

**Files:**
- Create: `outputs/seo-2026-minsk-uzda.json`

1. Supply credentials through environment variables and publish the batch.
2. Verify all 24 URLs return HTTP 200, contain `noindex`, the expected title/H1 and no `{Город...}` placeholders.
3. Inspect the first, middle and last pages in a browser at desktop and mobile widths; check FAQ, links, modal forms, console and horizontal overflow.
4. Run `C:\Users\user\.codex\scripts\harness.cmd smoke`.
5. Commit with `feat: generate seo route pages` and push `master`.
