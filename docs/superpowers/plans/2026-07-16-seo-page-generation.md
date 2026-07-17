# Full Minsk Route SEO Generation Plan

**Goal:** Publish 2,832 real pages (24 services × 118 unique destinations) with route-to-route internal linking.

**Architecture:** A frozen route catalogue mirrors the full existing site block. The pure renderer combines each route with each Excel row and injects 118 production links. A checkpointed MODX publisher creates only marker-owned resources and resumes from its manifest.

### Task 1: Restore the complete route catalogue

- Add six regional groups and 118 unique destinations.
- Remove the duplicate Lida entry and correct Buda-Koshelevo.
- Test counts and unique production aliases.

### Task 2: Render route-specific pages

- Mix the five Title, Description and intro variants independently and deterministically per query and destination.
- Keep Minsk as city 1 and do not generate reverse destination-to-Minsk pages.
- Replace all hard-coded Minsk–Uzda copy.
- Inject 118 real links for the current service query.
- Test that non-Uzda pages contain no leaked Uzda copy outside the catalogue.

### Task 3: Add production-safe MODX publishing

- Add an indexable production template.
- Page through the complete MODX resource list.
- Preflight every alias before mutation.
- Save a resumable manifest every ten resources.

### Task 4: Generate and publish

- Dry-run all 2,832 pages locally.
- Publish with progress checkpoints.
- Update the preview and the original 24 noindex pages so their city blocks use real links.

### Task 5: Verify and deliver

- Verify manifest count, HTTP status, metadata, H1, marker and 118 internal links.
- Browser-check representative service/city combinations on desktop and mobile.
- Run all tests and the global smoke harness, then commit and push.
