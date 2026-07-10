# Route Page Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one production-quality static preview page for «Перевозка грузов Минск — Узда» as the approved reusable visual template for future SEO generation.

**Architecture:** A dependency-free static page keeps the preview portable to the existing OpenCart/PHP site once hosting access works. Semantic HTML owns content and accessibility, one CSS file owns tokens/layout/responsive behavior, and one small JavaScript module owns menu/form behavior without sending data.

**Tech Stack:** HTML5, CSS3, vanilla JavaScript, Python 3.10+ `unittest`, Python `http.server`, global project harness.

## Global Constraints

- Do not implement Excel-driven page generation or mass page creation.
- Use only real client photographs supplied in `C:\Users\user\Downloads\Telegram Desktop`.
- Keep the current brand identity: true white, graphite, orange CTA, green only for messengers.
- One visible H1: `Перевозка грузов Минск — Узда`.
- Form behavior is local-only and must not transmit data.
- All source/config text files use UTF-8; code identifiers and filenames use ASCII.
- Desktop and mobile layouts must remain usable without horizontal page overflow.

---

### Task 1: Semantic page and real-photo asset set

**Files:**
- Create: `index.html`
- Create: `assets/photos/truck-open.jpg`
- Create: `assets/photos/truck-side.jpg`
- Create: `assets/photos/van-white.jpg`
- Create: `assets/photos/motorcycle-loading.jpg`
- Create: `assets/photos/boxes-loaded.jpg`
- Create: `assets/photos/night-route.jpg`
- Create: `assets/photos/van-cargo.jpg`
- Create: `assets/photos/fleet.jpg`
- Create: `tests/test_template.py`

**Interfaces:**
- Consumes: design tokens and section order from `docs/superpowers/specs/2026-07-11-route-page-template-design.md`.
- Produces: semantic DOM IDs `hero`, `route`, `prices`, `private-clients`, `business-clients`, `process`, `fleet`, `benefits`, `gallery`, `faq`, `contact`, `cities`.

- [ ] **Step 1: Write the failing structural tests**

```python
def test_page_has_one_route_h1(self):
    self.assertEqual(self.document.headings["h1"], ["Перевозка грузов Минск — Узда"])

def test_required_sections_are_present(self):
    self.assertTrue(REQUIRED_SECTION_IDS.issubset(self.document.ids))

def test_gallery_uses_real_images_with_alt_text(self):
    gallery_images = [image for image in self.document.images if image["inside_gallery"]]
    self.assertGreaterEqual(len(gallery_images), 6)
    self.assertTrue(all(image["src"].startswith("assets/photos/") and image["alt"] for image in gallery_images))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_template -v`
Expected: FAIL because `index.html` does not exist.

- [ ] **Step 3: Copy the selected real photographs**

```powershell
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_4_2026-07-10_23-50-54.jpg" "assets\photos\truck-open.jpg"
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_5_2026-07-10_23-50-54.jpg" "assets\photos\truck-side.jpg"
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_24_2026-07-10_23-50-54.jpg" "assets\photos\van-white.jpg"
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_23_2026-07-10_23-50-54.jpg" "assets\photos\motorcycle-loading.jpg"
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_27_2026-07-10_23-50-54.jpg" "assets\photos\boxes-loaded.jpg"
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_18_2026-07-10_23-50-54.jpg" "assets\photos\night-route.jpg"
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_29_2026-07-10_23-50-54.jpg" "assets\photos\van-cargo.jpg"
Copy-Item "C:\Users\user\Downloads\Telegram Desktop\photo_26_2026-07-10_23-50-54.jpg" "assets\photos\fleet.jpg"
```

- [ ] **Step 4: Implement the complete semantic page**

Create `index.html` with one `header`, one `main`, the exact section IDs above, one H1, H2/H3 hierarchy, price table, two eight-item service lists, four ordered process steps, three fleet entries, six gallery figures, six native `details` FAQ items, city links, real `tel:`, `mailto:`, Viber, WhatsApp and Telegram links, and a non-networked form with `data-demo-form`.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m unittest tests.test_template -v`
Expected: all structural tests PASS.

### Task 2: Design-system CSS and local interactions

**Files:**
- Create: `assets/styles.css`
- Create: `assets/app.js`
- Modify: `tests/test_template.py`

**Interfaces:**
- Consumes: DOM hooks from Task 1.
- Produces: responsive layout at 360–1440 px, focus states, reduced-motion support, menu state via `data-menu-open`, local form success via `data-form-status`.

- [ ] **Step 1: Add failing asset and behavior-contract tests**

```python
def test_page_loads_local_css_and_script(self):
    self.assertIn("assets/styles.css", self.html)
    self.assertIn("assets/app.js", self.html)

def test_form_is_demo_only(self):
    self.assertIn('data-demo-form', self.html)
    self.assertNotRegex(self.html, r'<form[^>]+action=["\']https?://')

def test_responsive_and_reduced_motion_contracts_exist(self):
    css = Path("assets/styles.css").read_text(encoding="utf-8")
    self.assertIn("@media (max-width: 760px)", css)
    self.assertIn("prefers-reduced-motion", css)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_template -v`
Expected: FAIL because CSS and JavaScript files do not exist.

- [ ] **Step 3: Implement CSS from the three concept images**

Define `--color-bg`, `--color-surface`, `--color-text`, `--color-muted`, `--color-accent`, `--color-accent-dark`, `--color-dark`, `--radius-lg`, `--radius-md`, `--container`. Implement sticky header, two-column hero, open editorial lists, semantic table, process rail, horizontal fleet rows, gallery, accordion, CTA/contact panel, focus-visible states, 760 px mobile collapse and reduced-motion override.

- [ ] **Step 4: Implement small local-only JavaScript**

```javascript
menuToggle.addEventListener("click", () => {
  const open = header.toggleAttribute("data-menu-open");
  menuToggle.setAttribute("aria-expanded", String(open));
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  status.textContent = form.checkValidity()
    ? "Заявка заполнена — позвоните или напишите нам для расчёта."
    : "Заполните имя и телефон.";
});
```

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m unittest tests.test_template -v`
Expected: all tests PASS.

### Task 3: Preview, visual QA, documentation and publication readiness

**Files:**
- Modify: `README.md`
- Create: `docs/fidelity-ledger.md`

**Interfaces:**
- Consumes: completed static page and concept PNGs.
- Produces: reproducible preview command, desktop/mobile screenshots, written fidelity evidence and deployable repository state.

- [ ] **Step 1: Start the local preview**

Run: `python -m http.server 4173 --bind 127.0.0.1`
Expected: `http://127.0.0.1:4173/` serves the template.

- [ ] **Step 2: Verify desktop and mobile in Browser/IAB**

Check desktop 1440×900 and mobile 390×844. Confirm page load, nav/menu, phone links, FAQ, local form feedback, no console errors and no horizontal overflow.

- [ ] **Step 3: Compare screenshots with concepts**

Use `view_image` for all three concept files and the latest desktop/mobile screenshots. Record at least five comparison points in `docs/fidelity-ledger.md`: copy, hero layout, typography, palette, real-photo treatment, section rhythm, responsive collapse and interactions.

- [ ] **Step 4: Run project checks**

Run: `python -m unittest tests.test_template -v`
Expected: all tests PASS.

Run: `C:\Users\user\.codex\scripts\harness.cmd smoke`
Expected: PASS without Ollama.

Run: `git diff --check`
Expected: no whitespace errors.

- [ ] **Step 5: Document preview and deployment boundary**

Update `README.md` with the local preview command, source-photo policy, current single-page scope and the fact that server publication requires working Beget/OpenCart credentials.

- [ ] **Step 6: Commit and push**

```powershell
git add -A
git commit -m "feat: build route landing page template"
git push
```
