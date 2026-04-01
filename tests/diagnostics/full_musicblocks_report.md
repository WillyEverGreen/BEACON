# ♿ Accessibility Audit Report

**URL:** https://musicblocks.sugarlabs.org/
**Scan Mode:** DEEP
**Date:** 2026-03-28 20:32 UTC
**Scan Time:** 40.2s
**Engines:** browser-probe, static, heuristic, axe-core, cognitive

---

## 📊 Executive Summary

### Accessibility Score: 🔴 **0/100**

| Severity | Count |
|----------|-------|
| 🔴 Critical | 15 |
| 🟠 Serious | 52 |
| 🟡 Moderate | 6 |
| 🟢 Minor | 0 |
| **Total** | **73** |

### 🧠 Cognitive Accessibility

**Cognitive Score:** 🟡 70/100

- **Readability Grade:** 21.0
- **Reading Ease:** 0/100
- **Jargon Density:** 0.0%
- **Navigation Complexity:** medium
- **Form Usability:** good

---

## 🔍 Findings by Category

### 📝 Forms — label 🔴
*12 issue(s), worst: critical*

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#myMedia`

**HTML:**
```html
<input accept="image/*" class="file" id="myMedia" tabindex="-1" type="file"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="myMedia">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#myOpenFile`

**HTML:**
```html
<input accept=".ta, .tb, .html,.mid,.midi" class="file" id="myOpenFile" tabindex="-1" type="file"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="myOpenFile">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#myOpenPlugin`

**HTML:**
```html
<input accept=".json" class="file" id="myOpenPlugin" tabindex="-1" type="file"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="myOpenPlugin">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#audioInput`

**HTML:**
```html
<input accept=".mp3, .wav" class="file" id="audioInput" tabindex="-1" type="file"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="audioInput">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#myOpenAll`

**HTML:**
```html
<input class="file" id="myOpenAll" tabindex="-1" type="file"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="myOpenAll">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#paste`

**HTML:**
```html
<input class="ui-autocomplete" id="paste" name="paste" placeholder="Paste Music Blocks code here" style="visibility:hidden" tabindex="-1" type="text"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="paste">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#fileName`

**HTML:**
```html
<input id="fileName" tabindex="-1" type="text"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="fileName">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#title`

**HTML:**
```html
<input id="title" tabindex="-1" type="text"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="title">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#author`

**HTML:**
```html
<input id="author" tabindex="-1" type="text"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="author">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#MIDICheck`

**HTML:**
```html
<input id="MIDICheck" tabindex="-1" type="checkbox"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="MIDICheck">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#guitarCheck`

**HTML:**
```html
<input id="guitarCheck" tabindex="-1" type="checkbox"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="guitarCheck">Label text</label> or aria-label="Label text".

---

#### 🔴 missing-label (critical)

**Issue:** Form input has no associated label. Screen readers cannot identify this field.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#search`

**HTML:**
```html
<input class="ui-autocomplete" id="search" name="search" placeholder="Search for Blocks" tabindex="-1" type="text"/>
```

**Confidence:** 64% (static)

**Fix:** Add <label for="search">Label text</label> or aria-label="Label text".

---

### 🎬 Media — media 🔴
*3 issue(s), worst: critical*

#### 🔴 missing-captions (critical)

**Issue:** Video element has no captions track. Deaf and hard-of-hearing users need captions.

**WCAG:** 1.2.2 (Level A)

**Element:** `video`

**HTML:**
```html
<video autoplay="" fetchpriority="high" loop="" muted="" playsinline="" style="width: 90%; height: 100%; object-fit: contain;">
<source src="loading-animation.webm" type="video/webm">
<source src="loading-animation.mp4" type="video/mp4">
</source></source></video>
```

**Confidence:** 64% (static)

**Fix:** Add <track kind="captions" src="captions.vtt" srclang="en" label="English">.

---

#### 🔴 missing-captions (critical)

**Issue:** Video element has no captions track. Deaf and hard-of-hearing users need captions.

**WCAG:** 1.2.2 (Level A)

**Element:** `video#camVideo`

**HTML:**
```html
<video id="camVideo" style="visibility:hidden;" tabindex="-1"></video>
```

**Confidence:** 64% (static)

**Fix:** Add <track kind="captions" src="captions.vtt" srclang="en" label="English">.

---

#### 🟠 autoplay-media (serious)

**Issue:** Media element has autoplay. Users must be able to control media playback.

**WCAG:** 1.4.2 (Level A)

**Element:** `video`

**HTML:**
```html
<video autoplay="" fetchpriority="high" loop="" muted="" playsinline="" style="width: 90%; height: 100%; object-fit: contain;">
<source src="loading-animation.webm" type="video/webm">
<source src="loading-animation.mp4" type="video/mp4">
</source></source></video>
```

**Confidence:** 63% (static)

**Fix:** Remove autoplay or provide controls to pause/stop within first 3 seconds.

---

### 📝 Forms — button 🔴
*1 issue(s), worst: critical*

#### 🔴 button-no-name (critical)

**Issue:** Button has no accessible name. Screen readers cannot identify this control.

**WCAG:** 4.1.2 (Level A)

**Element:** `button#submitLilypond`

**HTML:**
```html
<button class="confirm-button" id="submitLilypond"></button>
```

**Confidence:** 64% (static)

**Fix:** Add text content or aria-label="Button description".

---

### 🧭 Navigation — link 🟠
*35 issue(s), worst: serious*

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#link-to-sugarLabs`

**HTML:**
```html
<a href="https://www.sugarlabs.org/" id="link-to-sugarLabs" style="position: fixed; bottom: 20px; right: 20px;" target="_blank">
<div class="logo-container" id="bottom-right-logo">
<svg height="50" viewbox="0 0 501 167" width="150" xmlns="http://www.w3.org/2000/svg">
<!-- Logo paths -->
<path class=
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#record`

**HTML:**
```html
<a class="left tooltipped" data-tooltip="Record" data-tooltip-id="2055edaf-786e-4209-02a5-239b5108cbbf" id="record"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-html-beg`

**HTML:**
```html
<a id="save-html-beg"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-png-beg`

**HTML:**
```html
<a id="save-png-beg"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-html`

**HTML:**
```html
<a id="save-html"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-midi`

**HTML:**
```html
<a id="save-midi"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-svg`

**HTML:**
```html
<a id="save-svg"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-png`

**HTML:**
```html
<a id="save-png"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-wav`

**HTML:**
```html
<a id="save-wav"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-abc`

**HTML:**
```html
<a id="save-abc"> </a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-ly`

**HTML:**
```html
<a id="save-ly"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-mxml`

**HTML:**
```html
<a id="save-mxml"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-blockartwork-svg`

**HTML:**
```html
<a id="save-blockartwork-svg"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#save-blockartwork-png`

**HTML:**
```html
<a id="save-blockartwork-png"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#enUS`

**HTML:**
```html
<a id="enUS"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#enUK`

**HTML:**
```html
<a id="enUK"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#es`

**HTML:**
```html
<a id="es"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#pt`

**HTML:**
```html
<a id="pt"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#ja`

**HTML:**
```html
<a id="ja"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#kana`

**HTML:**
```html
<a id="kana"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#ko`

**HTML:**
```html
<a id="ko"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#zhCN`

**HTML:**
```html
<a id="zhCN"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#th`

**HTML:**
```html
<a id="th"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#tr`

**HTML:**
```html
<a id="tr"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#ayc`

**HTML:**
```html
<a id="ayc"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#quz`

**HTML:**
```html
<a id="quz"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#gug`

**HTML:**
```html
<a id="gug"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#hi`

**HTML:**
```html
<a id="hi"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#te`

**HTML:**
```html
<a id="te"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#ibo`

**HTML:**
```html
<a id="ibo"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#ar`

**HTML:**
```html
<a id="ar"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#bn`

**HTML:**
```html
<a id="bn"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#he`

**HTML:**
```html
<a id="he"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟠 empty-link (serious)

**Issue:** Link has no text content. Screen readers will announce it as empty.

**WCAG:** 2.4.4 (Level A)

**Element:** `a#ur`

**HTML:**
```html
<a id="ur"></a>
```

**Confidence:** 63% (static)

**Fix:** Add descriptive text or aria-label="description".

---

#### 🟡 unsafe-external-link (moderate)

**Issue:** Link opens in new tab without rel="noopener noreferrer".

**WCAG:** 3.2.5 (Level AA)

**Element:** `a#link-to-sugarLabs`

**HTML:**
```html
<a href="https://www.sugarlabs.org/" id="link-to-sugarLabs" style="position: fixed; bottom: 20px; right: 20px;" target="_blank">
<div class="logo-container" id="bottom-right-logo">
<svg height="50" viewbox="0 0 501 167" width="150" xmlns="http://www.w3.org/2000/svg">
<!-- Logo paths -->
<path class=
```

**Confidence:** 54% (static)
⚠️ *Needs manual review*

**Fix:** Add rel="noopener noreferrer" and "(opens in new tab)" for screen readers.

---

### ⌨️ Keyboard — keyboard 🟠
*11 issue(s), worst: serious*

#### 🟠 keyboard-unreachable (serious)

**Issue:** Only 1 of 17 interactive elements are keyboard reachable.

**WCAG:** 2.1.1 (Level A)

**Element:** `<body>`

**Confidence:** 61% (browser-probe)

**Fix:** Ensure all interactive elements can be reached via Tab key.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element a has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `a#link-to-sugarLabs`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#movabledo`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#fixed`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#myMedia`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#myOpenFile`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#myOpenPlugin`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#audioInput`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#myOpenAll`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input#paste`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

#### 🟠 no-focus-style (serious)

**Issue:** Element input has no visible focus indicator.

**WCAG:** 2.4.7 (Level AA)

**Element:** `input`

**Confidence:** 61% (browser-probe)

**Fix:** Add :focus styles with visible outline, border, or box-shadow.

---

### 📌 General — placeholder-as-label 🟠
*2 issue(s), worst: serious*

#### 🟠 placeholder-as-label (serious)

**Issue:** Input uses placeholder 'Paste Music Blocks code here' as its only label. Placeholders disappear when typing and are not a substitute for semantic labels.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#paste`

**HTML:**
```html
<input class="ui-autocomplete" id="paste" name="paste" placeholder="Paste Music Blocks code here" style="visibility:hidden" tabindex="-1" type="text"/>
```

**Confidence:** 63% (static)

**Fix:** Add a <label for="paste">Paste Music Blocks code here</label> or aria-label="Paste Music Blocks code here".

---

#### 🟠 placeholder-as-label (serious)

**Issue:** Input uses placeholder 'Search for Blocks' as its only label. Placeholders disappear when typing and are not a substitute for semantic labels.

**WCAG:** 1.3.1 (Level A)

**Element:** `input#search`

**HTML:**
```html
<input class="ui-autocomplete" id="search" name="search" placeholder="Search for Blocks" tabindex="-1" type="text"/>
```

**Confidence:** 63% (static)

**Fix:** Add a <label for="search">Search for Blocks</label> or aria-label="Search for Blocks".

---

### 🏗️ Structure — heading 🟠
*1 issue(s), worst: serious*

#### 🟠 no-headings (serious)

**Issue:** Page has no headings. Headings are essential for screen reader navigation.

**WCAG:** 1.3.1 (Level A)

**Element:** `<body>`

**HTML:**
```html
<body>
```

**Confidence:** 63% (static)

**Fix:** Add semantic headings (h1-h6). Each page should have exactly one h1.

---

### 📌 General — alt 🟠
*1 issue(s), worst: serious*

#### 🟠 svg-no-accessible-name (serious)

**Issue:** SVG element has no accessible name. Add a <title> child or aria-label.

**WCAG:** 1.1.1 (Level A)

**Element:** `svg`

**HTML:**
```html
<svg height="50" viewbox="0 0 501 167" width="150" xmlns="http://www.w3.org/2000/svg">
<!-- Logo paths -->
<path class="color-change" d="m63.05 117.52c-11.05 0-21.12-5.5-21.12-11.539 0-3.157 2.303-5.6
```

**Confidence:** 63% (static)

**Fix:** Add <title>Description</title> inside the SVG or aria-label="description".

---

### 📌 General — link-name 🟠
*1 issue(s), worst: serious*

#### 🟠 link-name (serious)

**Issue:** Ensures links have discernible text

**WCAG:** 2.4.4 (Level A)

**Element:** `#link-to-sugarLabs`

**HTML:**
```html
<a href="https://www.sugarlabs.org/" target="_blank" id="link-to-sugarLabs" style="position: fixed; bottom: 20px; right: 20px;">
```

**Confidence:** 74% (axe-core)

**Fix:** Links must have discernible text

**Code Fix:**
```html
Fix all of the following:
  Element is in tab order and does not have accessible text

Fix any of the following:
  Element does not have text that is visible to screen readers
  aria-label attribute does not exist or is empty
  aria-labelledby attribute does not exist, references elements that do not exist or references elements that are empty
  Element has no title attribute
```

---

### 🧠 Cognitive — readability 🟠
*1 issue(s), worst: serious*

#### 🟠 readability (serious)

**Issue:** Content readability is at grade level 21.0 (college level). COGA recommends grade 8 or below for broad accessibility.

**WCAG:** 3.1.5 (Level AAA)

**Element:** `<body>`

**Confidence:** 60% (cognitive)
⚠️ *Needs manual review*

**Fix:** Simplify language: use shorter sentences, common words, active voice.

---

### 📌 General — form 🟡
*2 issue(s), worst: moderate*

#### 🟡 missing-autocomplete (moderate)

**Issue:** Input likely collects personal data but missing autocomplete attribute.

**WCAG:** 1.3.5 (Level AA)

**Element:** `input#fileName`

**HTML:**
```html
<input id="fileName" tabindex="-1" type="text"/>
```

**Confidence:** 62% (static)

**Fix:** Add autocomplete="name" to this input.

---

#### 🟡 no-fieldset-legend (moderate)

**Issue:** Radio/checkbox group 'movable' not wrapped in <fieldset> with <legend>.

**WCAG:** 1.3.1 (Level A)

**Element:** `input[name="movable"]`

**HTML:**
```html
<input class="radioBtn" id="movabledo" name="movable" type="radio" value="true"/>
```

**Confidence:** 62% (static)

**Fix:** Wrap the group in <fieldset><legend>Group label</legend>...</fieldset>.

---

### 📌 General — aria 🟡
*1 issue(s), worst: moderate*

#### 🟡 no-aria-live (moderate)

**Issue:** Dynamic content container may need aria-live region for screen reader announcements.

**WCAG:** 4.1.3 (Level AA)

**Element:** `html.js.flexbox`

**HTML:**
```html
<html class="js flexbox canvas canvastext webgl no-touch geolocation postmessage no-websqldatabase indexeddb hashchange history draganddrop websockets rgba hsla multiplebgs backgroundsize borderimage borderradius boxshadow textshadow opacity cssanimations csscolumns cssgradients cssreflections csstr
```

**Confidence:** 49% (static)
⚠️ *Needs manual review*

**Fix:** Add aria-live="polite" or role="status" for non-urgent, aria-live="assertive" or role="alert" for urgent.

---

### 📌 General — contrast 🟡
*1 issue(s), worst: moderate*

#### 🟡 small-font-size (moderate)

**Issue:** Font size 1px may be too small for readability.

**WCAG:** 1.4.4 (Level AA)

**Element:** `div#loadingText`

**HTML:**
```html
<div class="loading-text" id="loadingText" style="color:#333; margin-top: 2rem; min-height: 1.5em; font-size: 1.2rem;">
</div>
```

**Confidence:** 49% (static)
⚠️ *Needs manual review*

**Fix:** Use at least 16px for body text. Ensure text can be resized to 200%.

---

### 🧭 Navigation — nav 🟡
*1 issue(s), worst: moderate*

#### 🟡 missing-skip-link (moderate)

**Issue:** Page with navigation lacks a 'skip to main content' link as the first focusable element.

**WCAG:** 2.4.1 (Level A)

**Element:** `<body>`

**HTML:**
```html
<body>
```

**Confidence:** 62% (static)

**Fix:** Add <a href="#main-content" class="skip-link">Skip to main content</a> as the first element in <body>.

---

## 📋 Recommendations

1. **Fix 15 critical issues immediately** — these prevent some users from accessing content
2. **Address 52 serious issues** — these significantly impact accessibility
3. **Review 6 moderate issues** — these affect user experience
4. **Manually verify 4 flagged items** — automated checks have lower confidence

---
*Report generated by Accessibility Intelligence Engine — 2026-03-28 20:32 UTC*