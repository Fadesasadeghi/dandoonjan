## Current desktop lower-landing handoff — 2026-10-02

Owner review pending. One below-the-fold implementation pass completed; no second
visual iteration. Hero frozen: HTML header/navigation through feature row unchanged,
first740px of1440x900 capture pixel-identical to premium-finish baseline, and
approved tooth/ellipse/heading/description/CTA geometry regression unchanged.

Changed this pass:
- frontend/index.html: compact semantic information panel; editorial/process card;
  FAQ composition wrappers, existing native details/summary and FAQ text retained.
- frontend/landing.css: desktop-only lower-page lighting, editorial glass, information
  panel and rounded glass FAQ styles; no changes to hero CSS declarations.
- verification/test_landing_browser.py: reproduced seam regression, frozen hero
  pixel check, native FAQ keyboard/marker checks, focused captures and additional
  rendered contrast coverage for process text and expanded FAQ answers.
- This README and VERIFICATION.md; fresh evidence under
  evidence/reference-match/lower-desktop-pass/.

Information panel retains synthetic-case qualification, explicit offline no actual
image interpretation, no result-time guarantee, do not use sensitive information,
discussion/evidence aid boundary, and not a substitute for examination/diagnosis/
treatment prescription. Existing start-sample and conditional resume IDs/handlers
remain unchanged. Dark-teal readable copy, neutral info line icon,30px glass corners,
thin white border and controlled padding; no emergency/alarm styling.

Editorial introduction remains Persian RTL, right column eyebrow/46px heading/
existing question-start sentence. Left32px-corner process/story card preserves
explanatory meaning, with native ordered list: documents/explanation -> organizing
evidence -> identifying uncertainty -> questions for dentist. Four original local
line SVGs and thin connector; no diagnosis/autonomous image-interpretation claim.
A faint oversized ellipse and broad feathered glows add restrained depth.
FAQ section has eyebrow/40px heading, three22px-corner glass accordions, teal
questions and custom CSS chevrons, subdued focus/hover and expanded states. Native
keyboard Enter/Space expansion/collapse preserved. Orange markers removed only
within desktop home FAQ; downstream controls/styles untouched.

The1100px old fixed-background cutoff was reproduced before implementation:
x10 changed RGB152,211,222->158,215,224 across1099/1100(maxdelta6; regression
limit3). Lower wrapper masks its continuous aqua background in over260px, fully
covering cutoff, then gently fades toward footer. The new regression passes at
x10,50,1380,1430. Hero background/pixels remain unchanged. No horizontal overflow.

FINAL scoped offline browser run:14passed,1failed in40.20s. Desktop composition,
frozen geometry/pixels,local fonts/pills/feature visibility,asset,keyboard/create,
real synthetic sample/case-edit/reprocess/resume,home-only header,background seam
and native FAQ behavior all pass. Entire rendered contrast test ran(no skipped/
xfail/excluded failure): retained hero white-text contrast conflict remains the
sole failing test. New lower-section text samples all pass; minimum6.042:1,
including safety panel,process labels and all three expanded FAQ answers.
Large-text3:1/normal-text4.5:1 thresholds and glyph methodology retained.
This is NOT full-page accessibility completion because hero conflict remains.

Screenshots(width1440,CSS viewport900; full-page includes all FAQ answers open):
- landing-1440-full.png
- landing-1440-transition.png
- landing-1440-editorial.png
- landing-1440-faq.png
All four opened/inspected: no hard color seam; organized safety/demo panel; coherent
editorial/process hierarchy; rounded glass FAQ with no legacy orange; whitespace
is intentional but bounded. Lower dark-teal text is more editorial than the white
hero hierarchy; informational panel is necessarily text-dense. Exact desktop
visual acceptance still pending; no owner-browser/assistive-technology audit.

Source hashes confirm tooth/app.js/landing.js/styles.css unchanged; downstream
HTML byte-identical and hero HTML unchanged. Backend/provider code untouched.
No tablet/mobile adaptation or verification; shared semantic HTML changes exist
but desktop styling is scoped to min-width1051. No external/provider requests,
paid service,commit,push,deploy. Working tree remains uncommitted; HEAD unchanged.
git diff --check passed. Previous reports below are historical evidence only.

## Latest premium desktop finish checkpoint — 2026-10-02

One visual website pass only; owner review pending. Frozen approved geometry
preserved exactly: tooth, three ellipses, heading, description and both CTAs have
zero x/y/width/height delta against measured-composition-pass. Scope desktop only.
Evidence `evidence/reference-match/premium-finish-pass/landing-1440.png`,
full-page counterpart, desktop-junit.xml, desktop-geometry.json,
frozen-geometry-deltas.json, protected-integrity.json, rendered-local-fonts.json
and landing-contrast-1440.json. Reference and new capture both visually opened
and directly compared after this pass.

FONT INVESTIGATION BEFORE WEBSITE EDITS:
Read all357 local Windows system/user TTF/OTF/TTC files; zero parse errors.
Cmap audit checks exact heading plus Persian پچژگکی, covering18 families:
Aldhabi,Andalus,Arabic Typesetting,Arial,Calibri,Courier New,Dubai,Sakkal Majalla,
Microsoft Sans Serif,Microsoft Uighur,Segoe UI,Simplified Arabic,Simplified Arabic
Fixed,Tahoma,Times New Roman,Traditional Arabic,Urdu Typesetting,B Nazanin.
All18 rendered exact two-line heading in offline Chrome contact sheet;
CDP confirms actual local fonts (not remote/custom) for every candidate.
Audit script and JSON/contact sheets retained locally in same evidence folder.
Best3 by visual comparison: Dubai,Calibri,Segoe UI. Dubai remains closest overall;
Calibri rounded but narrower/calligraphic terminals; Segoe UI more rigid. No
candidate clearly closer, so Dubai retained with64px/600/1.15 heading unchanged.
No fonts downloaded or shipped as production assets; availability varies by host.

CSS FINISH:
Exact #9ED7E0 base plus existing broad cyan-to-bluer-aqua gradient,1200+-scale
upper-left pale glow,820x650 feathered tooth glow and580x170 floor-light region.
No darker right field,panels,vignette or glyph outlines. Primary pearl gradient
#FCFDFD to#EDF4F6 with faint inset highlights; secondary/login milky white/aqua
translucent gradients,delicate white borders,7px backdrop blur and faint inset
edges. All dimensions/999px radii unchanged. Wordmark weight700->600 only.
Feature boxes66x66/18px corners retained,more luminous translucent gradient,
white top/left inset highlight,8px blur,no exterior drop shadow. Original shared
thin1.5-unit rounded SVG family preserved; artwork42->44px for more presence.
No icon library/dependency/remote assets.

Only feature row moved48px upward: box Y637->589; description box698.5..727.3.
Regression verifies complete features at width1440/CSS height740 (160px allowance
for browser/OS chrome relative to900 outer height); actual owner OS chrome/zoom
not directly reproduced. Following story padding+48 preserves its previous
placement while relocated safety/demo/resume content remains outside hero.
Reflection opacity.25->.36,height154 with scaleY(.62),rendered height95.5px,
.65px blur,downward mask fully transparent by145 unscaled px. Contact/tooth
position unchanged; compressed faded reflection stronger,not a second tooth.

FINAL scoped offline tests12passed,1failed in32.46s. Frozen geometry,new finish/
740-height visibility,composition,icons/no outlines,local fonts/pills,real synthetic
sample/create/resume flows,keyboard,header scope and approved asset pass.
Current contrast test executed unchanged in method/thresholds and FAILS:
heading1.605 vs3;description1.553 vs3;secondary1.574 vs4.5;wordmark1.765 vs4.5
(wordmark600/21px now normal text);auth1.330 vs4.5;features1.369-1.871 vs4.5;
nav also unresolved. Relocated clinical limitation5.302 vs4.5 passes. No skip,
xfail,hardcoded pass or lowered threshold. This is owner visual checkpoint only,
NOT accessibility-complete; remediation explicitly deferred by owner.

Direct visual comparison: softer lighting/glass,larger fine icon artwork,shorter
brighter reflection,complete features well inside first view. Remaining differences:
Dubai shape differs from reference; wordmark/header finer; reference lighting has
more photographic nuance; reference secondary border more visible; feature row
now higher than reference to accommodate browser chrome; custom icons and approved
tooth differ inherently; truthful descriptions remain different. No second pass.

Changed this pass:frontend/landing.css,verification/test_landing_browser.py,
these2gate documents and new premium-finish-pass evidence/font-audit artifacts.
frontend/index.html unchanged this pass. Protected tooth/app.js/landing.js/styles.css
hashes unchanged; backend/provider code untouched. No tablet/mobile media edits
or tablet/mobile checks. git diff --check passed. No external/provider requests,
commit,push,deploy. Working tree uncommitted. Earlier reports below are history.

## Latest measured composition checkpoint — 2026-10-02

One desktop-only visual pass; owner review pending. Reference inspected before
edits; reference 1672x941 normalized uniformly to width1440 (height810.4).
Approximate reference ink/geometry: header top30; logo1165,37 162x34;
nav694-1121; login114,30 148x50; tooth253,174 332x400; heading878,205
448x130; description ink379-430; CTA486 280x69 and208x69; features646
65x65; title baseline740/description769. Screenshot estimates are not DOM facts.
Reference ellipse bounds146,109 342x336;332,179 383x407;179,329 497x269.

Previous actual screenshot: tooth339x421 at254,174; heading ink approximately
480x136 at850,195; Dubai68/700, linebox502x156.4; description ink407-468;
CTA527; boxes643; feature title baseline741/descriptions773. Already all visible.

New browser geometry in `evidence/reference-match/measured-composition-pass/desktop-geometry.json`:
header110,27 1220x56; brand1164.5,34.5 165.5x40.9; nav724.1,28.4 408.4x53.1;
login110,30 148x50; tooth imagebox222,140 399x454, alpha silhouette approx324x402
at258,172. PNG unchanged. Three ellipse bounds exactly retained; opacity gently
raised. Reflection/contact floor repositioned with smaller displayed tooth.
Heading Dubai64/600/1.15; linebox828,193 502x147.2, screenshot ink approximately
452x128 (not a font-box measurement). Description828,364.2 502x81.6;
heading->description container gap24, description->CTA40; CTA485.8.
Old approximate container gaps56 and48 reduced to24 and40. Feature boxes637,
66x66; title box712..743.5; descriptions746.5..775.3. Estimated screenshot
baselines titles733/descriptions764. All four complete in1440x900.

SVG artwork40->42px; stroke1.6->1.5; additional document rule, brain folds,
clock diagonal ticks and shield interior contour. Shared rounded caps/joins.
Glass boxes slightly luminous, inset highlight only; no drop shadow. Pills keep
280x69/208x69/148x50,999px radii; primary#F4F8F9/no border; lighter labels,
secondary1px translucent border, auth softened1px. Broad low-opacity illumination
added around tooth/copy without darkening base/right side or adding halos.

FINAL scoped offline tests: 11 passed,1 failed in23.58s. Composition, measured
rhythm, asset/geometry, local Dubai fonts, pills, no outlines, real create/sample/
resume, keyboard and home-only header pass. Contrast still fails, unskipped:
heading1.675 vs3,description1.604 vs3,secondary1.639 vs4.5,brand1.786 vs3,
auth1.319 vs4.5; nav/features also remain unresolved. Full rendered RGB/ratio
records in landing-contrast-1440.json. WCAG large/normal thresholds unchanged.
No claim of accessibility completion. Owner requested visual checkpoint with
known failure documented; no automatic second visual iteration.

Both reference and final1440 screenshot opened directly for comparison. Main
CTA vertical position now aligns. Font character/weight remains different;
heading screenshot lettering differs; nav is narrower/rightward than reference;
feature boxes about9px high; approved tooth has different inherent form and is
about8px narrower than reference after aspect-preserving size reduction; reflection
is fainter. Truthful feature descriptions differ. Overall first viewport complete,
no safety/demo clutter below CTA; those remain in following explanatory section.

Protected tooth/app.js/landing.js/styles.css hashes unchanged; backend untouched.
No tablet/mobile edits to media rules or tests run there (shared SVG changes apply
there; NOT VERIFIED). No provider/network request,commit,push,deploy. Changed:
frontend/landing.css,index.html,verification/test_landing_browser.py,two gate docs
and new measured-composition-pass evidence. git diff --check passed. Older results
below are historical, not current contrast acceptance.

## Latest desktop soft visual-language pass — 2026-10-02

Owner review pending; one website visual pass, no second visual iteration.
Evidence: `evidence/reference-match/soft-language-pass/landing-1440.png`,
`landing-1440-full.png`, `desktop-junit.xml`, `landing-contrast-1440.json`,
`rendered-local-fonts.json`, `protected-integrity.json`.

Local Windows fonts inspected: Dubai regular/light/medium/bold, Segoe UI and
Tahoma available. Chrome CDP confirms Dubai-Bold heading, Dubai-Regular
paragraph, Dubai-Medium navigation/features, all local noncustom fonts.
Dubai selected for softer rounded Persian forms; no download or new asset.
Heading 68px/700/1.15, description 26px/400/1.57, navigation 18px/500,
CTA 20px/500, features 21px/500 and 18px/400. No glyph outlines/shadows.

Background exact base #9ED7E0 plus broad 110-degree gradient through #91CEDB
to #73B8CF and large feathered #D5F1F455 upper-left illumination. No rectangle,
vignette or dark teal local field. White/light nav/wordmark/feature text restored.
Primary 280x69px, secondary 208x69px, auth placeholder 148x50px; all 999px
radius. Primary soft white/no border; secondary 1.5px translucent border;
auth 1px translucent border. Local decorative camera outline and chevron added.
66px glass feature containers/18px corners, 40px white line art retained.

Sample handler/control, synthetic/offline qualification, clinical limitation
and conditional resume moved into `.landing-product-context` at start of the
following `.landing-story`, after the four hero features. Visible and accessible,
not deleted. Truthful feature descriptions remain; AI/speed/privacy qualifications
are in that following section. No backend capability changed.

FINAL scoped offline desktop tests: 10 passed, 1 failed in 23.21s. Geometry,
composition, real sample/create/resume flow, keyboard, local fonts, pill sizes,
no text outlines, placeholder and home-only header all pass. Contrast test fails
without skip/xfail: heading 1.679 vs 3; description 1.643 vs 3; secondary 1.692
vs 4.5; wordmark 1.808 vs 3; auth 1.331 vs 4.5; active home 4.157 vs 4.5;
other navigation 1.557-1.713 vs 4.5; features 1.460-1.887 vs 4.5.
Relocated safety/sample text passes 5.302-5.315 vs 4.5. Correct WCAG large-text
threshold retained (24px regular or 18.6667px bold), normal text 4.5.
This light-white visual target conflicts with measured contrast: NOT accessibility
complete. No background darkening or test bypass performed to conceal this.

Reference and final screenshot directly opened and compared: cleaner cyan
lighting and light UI; no clutter below CTA; pills/custom icons/glass treatment
closer. Local font still not exact; paragraph/CTA block about 35-40px lower than
width-normalized reference; local letters differ; reference lighting somewhat
bluer. Reference camera is fuller and arrow points differently. Tooth/circle
geometry/asset unchanged; feature icons slightly finer than reference; some
feature descriptions remain truthful alternatives. Further correction stopped
for owner review, not auto-iterated.

Protected hashes unchanged: tooth, app.js, landing.js, styles.css; backend/provider
untouched. No tablet/mobile adaptation/testing this pass; shared HTML relocation
is NOT VERIFIED there. git diff --check passed. No commit/push/deploy/provider or
external network request. Changed this pass: frontend/index.html,
frontend/landing.css, verification/test_landing_browser.py and these two docs;
new evidence folder. Prior results below are historical only.

## Current desktop review pass — 2026-10-02: NOT APPROVED / PARTIALLY VERIFIED

One visual pass, no further visual corrections after screenshot comparison. Evidence:
`evidence/reference-match/clean-type-pass/landing-1440.png`, `desktop-junit.xml`,
`landing-contrast-1440.json`. Actual website changed, no mockup.

All visible text shadows/strokes removed; regression verifies none on hero,
header, controls and features. Original inline SVG document/brain/clock/shield
icons share 40px artwork, 1.6-unit white round strokes and existing 66px glass
containers. Tooth asset/circle geometry unchanged. Reference heading/description,
nav, CTA labels and feature titles transcribed. No separate reference eyebrow.
Reference descriptions for guidance used exactly; AI feature explicitly qualified
as offline demo. Reference minute-result/confidentiality guarantees not asserted;
truthful scope warnings used. “بیشتر بدانید” links to real explanation; sample
handler retained on separate visible sample control. Auth remains disabled.

Desktop-only run: 9 passed, 1 failed in 24.43s. Geometry, clean typography/icons,
copy/placeholder, keyboard/create, home-only header, asset and synthetic case
flows passed. Rendered contrast FAILED: heading/em 2.400 vs 3; description 2.171
vs 3; sample link/note 3.962 vs 4.5; clinical limitation 4.359 vs 4.5. No skipped
or xfailed checks. Appropriate WCAG large-text threshold now 3:1 at >=24px,
or >=18.6667px bold; normal text stays 4.5:1. Actual glyph backdrops measured
without outlines. This is not an accessibility-complete implementation.

Direct image inspection: clean glyphs and closer custom icons; font differs,
nav/brand/features/secondary CTA use teal rather than reference white. Feature
row is about 20px lower due to wrapped truthful notice/sample control. Background
remains brighter left with a broad deeper aqua copy region; hero contrast remains
insufficient at its lightest glyph backgrounds. No additional pass performed.

Changed this pass: frontend/index.html, frontend/landing.css,
verification/test_landing_browser.py, verification/test_p1_browser.py,
these two gate documents and new clean-type-pass evidence. Tablet/mobile NOT
VERIFIED, no intentional responsive tuning. app.js, landing.js, styles.css,
backend/provider code and approved tooth unchanged. No provider/network calls,
commit, push or deployment. Working tree remains uncommitted. Prior reports below
are historical and their passing contrast results do not apply to this version.

# Current desktop reference-copy pass — 2026-10-02

**VERIFIED WORKING in the tested desktop Chrome/SQLite/Mock scope. Owner visual
acceptance pending.** Only the desktop was worked on or tested in this pass.
The current reference is `docs/ui-redesign/reference/aqua-landing-target.png`.

## Fresh final results

**10 passed in 26.22s**:

- Landing composition [1440 × 900], desktop reference geometry, approved heading/
  description/header and disabled login-placeholder behavior.
- Rendered contrast [1440 × 900]; keyboard/reduced motion/create; home header
  isolation; approved PNG dimensions/alpha; finite normal-motion recording.
- Existing synthetic sample/responsive/print flow at **1440 only**, plus existing
  edit/add-evidence/reprocess/resume flow from `test_p1_browser.py`.

[Final JUnit](evidence/reference-match/approved-copy-pass/final-desktop-junit.xml),
[contrast measurements](evidence/reference-match/approved-copy-pass/landing-contrast-1440.json),
[source boundary checks](evidence/reference-match/approved-copy-pass/source-checks.json).

Previous complete-suite counts below are historical, not reruns in this pass.
The first capture run passed three tests and found small-text contrast failures.
The second passed three tests and still caught thin glyph edges and the new FAQ
summary inheriting a light downstream colour. Those were corrected with a deeper
**glyph-local shadow**, not a darker page field, and home FAQ text colour scoping.
The final ten-test run above is the completed verification result.

## Contrast methodology and results

Paired full-page browser captures preserve the actual layout/lighting. The first
includes ink; the second hides only foreground ink while retaining explicit CSS
text-shadow colour and geometry. The pixel difference identifies actual glyph
interiors (at least 50% foreground coverage), avoiding container whitespace,
rounded button corners and unrelated decorative symbols. Every sampled text
still requires **≥4.5:1**, including large text; no exclusions, xfail or hardcoded
passing ratio. A halo is part of the real rendered backdrop, not added by the
test. The production CSS visibly applies it in ordinary browser rendering.

**28 text/control samples**, all passed. Minimum **4.5528709754:1** for one feature
description. Heading minimum **7.6731072230:1**, foreground RGB (247,250,251),
worst composited local backdrop RGB (38,86,103), at (1101,319), 12,480 glyph samples.
The stronger local contrast is supplied by the text shadow; the global aqua
background alone does not support literal white normal text at 4.5:1.

This is scoped rendered-pixel evidence, not comprehensive accessibility or a
screen-reader certification. Browser antialias fringes are not foreground colours
for this check. Header placeholder is disabled, accessible name/title say future
availability, forced activation produced no requests or view change.

## Direct reference comparison

Three desktop captures were directly opened beside the exact target: initial
approved-copy build, header/font/shadow correction, and final contrast correction.
[First](evidence/reference-match/approved-copy-pass/capture-1-1440.png),
[second](evidence/reference-match/approved-copy-pass/capture-2-1440.png),
[final](evidence/reference-match/approved-copy-pass/landing-1440.png).
These are actual Chrome website screenshots. No raster/image generation tool was
used. The reference is not requested or embedded by the production page.

Final: headline now has the exact words and two lines, nearly the target width
and vertical placement; header has the four requested links, English wordmark and
far-left inactive login pill. Background is one airy light aqua field rather than
a dark copy-side panel. Existing three overlapping pale outlines, approved tooth
silhouette, fading reflection and CTA proportions remain. The four feature groups
now use light text on translucent icon containers at the matched desktop height.

Specific remaining differences: local Segoe UI/Arial Narrow font shapes differ
from the raster's unidentified fonts; accessibility shadows are visible as thin
halos around white text, stronger than the reference's clean light lettering.
Safety/offline/synthetic notices remain below the actions. CTA labels and feature
labels/icons describe real create/sample/evidence/discussion behavior rather than
reference-only camera, speed, privacy or image-analysis claims. The tooth remains
within the approved ~339 × 421px range, slightly taller/lower at the roots than
the width-normalized reference. Owner acceptance is not claimed.

## Source, scope and stop

Modified in this pass: `frontend/index.html`, `frontend/landing.css`,
`verification/test_landing_browser.py`, `verification/test_p1_browser.py`,
`docs/ui-redesign/gate-1/README.md`, `docs/ui-redesign/gate-1/VERIFICATION.md`, plus
fresh evidence under `evidence/reference-match/approved-copy-pass/`.
`test_next_phase_browser.py` still contains an earlier authorized uncommitted
change; it was not changed or rerun in this desktop pass.

Approved asset, app.js, landing.js and styles.css are byte-identical to this pass's
starting hashes. Backend has no diff. DOM from `#view-workspace` onward remains
identical to HEAD. No source asset was cropped/regenerated or overwritten. No
real credentials, external provider, paid service, deployment, commit or push.
`git diff --check`: passed. HEAD unchanged:
`7ef5dfafa440d2603d1b9c4ff9f29fcb2b5633d8`; implementation remains uncommitted.

**NOT VERIFIED:** 768/390 layouts after the new copy/header; other browser engines,
physical devices, every hover/zoom/screen-reader state; production/provider/clinical
acceptance. No broader regression-suite result is asserted for this pass.

Stop for owner desktop visual review.

---

## Earlier verification (historical)

# Aqua landing verification — 2026-10-01

**VERIFIED WORKING in the tested local synthetic Chrome scope.** Owner visual
acceptance of this new aqua landing is **NOT VERIFIED / pending review**. Prior
visual acceptance below applies to the older charcoal asset only.

## Recorded pre-change state

HEAD was `7ef5dfafa440d2603d1b9c4ff9f29fcb2b5633d8`; no tracked changes.
Existing untracked items: `DANDOONJAN_SADEGHI_NEXT_PHASE.zip`,
`frontend/hero-tooth-aqua.png`, `frontend/landing-tooth-small.webp`,
`frontend/landing-tooth.webp`, and `tools/`. Existing page used a dark charcoal
scene and `/ui/hero-tooth.png` (1312 × 1199). The newly written asset regression
failed against that source before implementation: **1 failed**, expected the
approved aqua asset. This is the targeted pre-change reproduction, not a clean
full-suite baseline. The default Linux Python lacked pytest/Pillow; verification
used the existing Windows virtual environment with approved WSL interop.

## Checks run at this gate

Focused landing run: **12 passed** (includes three contrast viewports).
Final full offline regression: **419 passed, 2 skipped, 3 existing deprecation warnings** (162.07s).
Suites: `tests`, `verification/test_landing_browser.py`,
`verification/test_p1_browser.py`, `verification/test_next_phase_browser.py`,
`verification/test_next_phase_runtime.py`. Final run has **no `-k` exclusions**. The two skips are existing directory-symlink
read/write tests: Windows lacked the privilege to create directory symlinks.
The warnings concern existing FastAPI/Starlette deprecations.
JUnit: [focused](evidence/aqua-landing/landing-junit.xml),
[full regression](evidence/aqua-landing/full-regression-junit.xml).

Browser fixture launches a local FastAPI site with temporary SQLite, synthetic
cases and Mock; live providers explicitly disabled and credential variables
blanked. No dependency installation, remote asset fetch or paid service.
Browser navigation checks cover create, synthetic sample, conditional resume,
case editing, adding evidence, processing/report flow and printing. Runtime
verification checks five synthetic cases concurrently, restart persistence,
source isolation and content-free logs. Fresh compatibility/runtime evidence is
under `evidence/aqua-landing/compatibility/`.

Both formerly failing desktop overflow regressions
`test_real_sample_responsive_and_print[1440]` and
`test_four_stages_reports_pdf_and_fallback[1440]` passed after the decorative-ring
fix. The 22-pass intermediate run excluded the old palette assertion; it is not
final acceptance. The first complete strengthened run had 414 passed, 5 failed,
2 skipped: four failures identified tablet/mobile title backgrounds below the
retained 4.5:1 threshold, and one identified an incorrect downstream colour in
the new test. The light field was extended, and the test was corrected to the
existing downstream `#111412`; no downstream style was changed.

## Contrast assertion correction

The older `test_rendered_palette_contrast` compared `body` and `.lede` foreground
colours only to `body.backgroundColor` and body gradient endpoints. It compared
primary button text only to `backgroundImage` gradient colours, missing solid
button backgrounds. It did not composite the home scene's translucent light
field. Thus it measured `#17627A` against bare `#9ED7E0` (4.3238:1), rather than
the background actually behind the copy. The accessibility requirement is valid;
that measurement method no longer represents the approved rendered design.

The updated assertion shares the landing sampler: record visible text colours
and rectangles, hide only text ink while preserving backgrounds, capture the
full rendered page, calculate relative luminance against sampled composited
background pixels, and require **every sample ≥ 4.5:1**. Sample within controls'
text-bearing interior to avoid their rounded transparent corners. Check all
three widths, including solid white/deep cyan CTAs, eyebrow, title, explanation,
sample notice, limitation, brand/header subtitle, lower editorial content and
footer. Even large titles retain the stronger 4.5:1 threshold.

15 visible samples at 1440/768px; 14 at 390px (existing mobile header subtitle is
hidden). Minimum ratios: **4.5185:1** at 1440/768px; **4.5524:1** at 390px.
[1440 measurements](evidence/aqua-landing/landing-contrast-1440.json),
[768 measurements](evidence/aqua-landing/landing-contrast-768.json),
[390 measurements](evidence/aqua-landing/landing-contrast-390.json).
This is scoped pixel sampling, not comprehensive accessibility certification.

## Fresh screenshots and direct visual inspection

| Viewport | Initial viewport | Full composition |
| --- | --- | --- |
| 1440 × 900 | [Desktop](evidence/aqua-landing/landing-1440.png) | [Full](evidence/aqua-landing/landing-1440-full.png) |
| 768 × 1024 | [Tablet](evidence/aqua-landing/landing-768.png) | [Full](evidence/aqua-landing/landing-768-full.png) |
| 390 × 844 | [Mobile](evidence/aqua-landing/landing-390.png) | [Full](evidence/aqua-landing/landing-390-full.png) |

All three viewport and full-page captures were directly inspected after the
visual fixes. Desktop: glossy supplied tooth is dominant on the left, separated
from large RTL title/copy/actions on the right. Actual alpha shows the aqua
scene through the root gap and around the natural silhouette. Curved lines and
soft CSS floor shadow integrate it without a card. Tablet: centered title,
350px image box, copy/actions/limitation form a balanced vertical composition.
Mobile: 250px image box, 20px horizontal breathing room, full-width primary and
immediately following secondary; Persian text and limitation are unclipped and
readable. Both actions and the limitation fit the specified initial viewport at
all widths. No horizontal overflow. Lower copy continues as spacious editorial
content, with no KPI/card grid. Exact body base is `rgb(158, 215, 224)`; translucent
white light fields raise text contrast while retaining the aqua environment.

Additional evidence: [enlarged text](evidence/aqua-landing/landing-390-large-text.png),
[failed image](evidence/aqua-landing/landing-390-fallback.png),
[keyboard focus](evidence/aqua-landing/landing-keyboard-focus.png),
[finite normal motion](evidence/aqua-landing/landing-normal-motion.webm).
Reduced motion disables all landing animations. Failed image preserves actions
and keyboard sample flow. Enlarged text expands vertically without horizontal
scrolling; it need not fit the initial fold.

## Repository boundary and remaining limitations

Downstream DOM from `#view-workspace` onward is identical to HEAD. `app.js`,
`styles.css`, `landing.js` and backend source have no diff. Home-only header
background disappears in workspace and returns on home. Asset bytes preserved;
no regeneration. Existing historical next-phase evidence overwritten by older
suite defaults during intermediate runs was restored from the initially clean
HEAD; those fresh intermediate outputs are retained in `prior-suite-output/`.
Final evidence destinations are isolated without changing runtime test source.

`git diff --check`: **passed**.
No commit created; HEAD remains the recorded SHA. Working tree contains only the
landing source/test/documentation changes, fresh review evidence and the original
untracked items. Owner review remains pending.

**NOT VERIFIED:** other browser engines, physical devices, screen-reader use,
all interactive contrast states, every native browser zoom implementation,
production/provider/clinical acceptance. Enlarged-text check is a CSS text-size
surrogate. System Persian typography remains Tahoma/Segoe UI/DejaVu, not a custom
Persian font. No claims of live-provider or deployment readiness.

---

## Historical verification (2026-09-30)

# Gate 1 verification — 2026-09-30

**VERIFIED WORKING within the local synthetic Chrome scope below.** Manual visual
acceptance was granted by the user on 2026-09-30 for the current Landing and
`frontend/hero-tooth.png`. No commit or push had occurred when this evidence was
recorded.

Branch: `agent/sadeghi-next-phase`.
Starting and current HEAD: `5262c3e82761e65acdad07f8fee1eeb2cd98f649`.
All implementation and evidence remain uncommitted. The supplied ZIP was not
opened, changed, added or deleted.

## Exact new execution results

Windows Python **3.11.3**, Chrome **154.0.8037.92**, Playwright **1.63.0**.
Local temporary SQLite/Mock fixture, live provider explicitly disabled. No new
runtime or verification dependency was installed.

| Executed scope | Passed | Skipped | Failed |
| --- | ---: | ---: | ---: |
| `tests/regression_p0` | 27 | 2 | 0 |
| `tests/regression_p1` | 29 | 0 | 0 |
| `tests/regression_rc` | 24 | 0 | 0 |
| `tests/next_phase` | 22 | 0 | 0 |
| Remaining `tests` | 109 | 0 | 0 |
| `verification/test_p1_browser.py` | 16 | 0 | 0 |
| `verification/test_next_phase_browser.py` | 6 | 0 | 0 |
| `verification/test_landing_browser.py` | 8 | 0 | 0 |
| **Complete run** | **241** | **2** | **0** |

Complete run: **121.21s**, three existing deprecation warnings (Starlette
TestClient/httpx, FastAPI `on_event` registration and internal implementation).
Both skips are directory-symlink containment cases, `read` and `write`, because
Windows lacks the directory-symlink privilege (WinError 1314). They are not passes
at this gate. Their prior Linux acceptance remains historical evidence only.

Complete command used the existing Windows Python environment, with
`DJ_LIVE_PROVIDER_ENABLED=false` and
`NEXT_PHASE_EVIDENCE=docs/ui-redesign/gate-1/evidence/compatibility` set inside the
Python process, then:

```text
pytest tests verification/test_p1_browser.py verification/test_next_phase_browser.py verification/test_landing_browser.py -q --tb=short --junitxml=docs/ui-redesign/gate-1/evidence/final-junit.xml
```

See [complete log](evidence/final-pytest.log) and [JUnit](evidence/final-junit.xml).
The run used the final tooth artwork. Subsequent desktop-only adjustments lowered
the caption, moved the tooth toward the center and placed the display words on one
line. After those changes, the complete landing suite was rerun:

```text
.venv/Scripts/python.exe -m pytest verification/test_landing_browser.py -q --tb=short --junitxml=docs/ui-redesign/gate-1/evidence/landing-final-junit.xml
```

**8 passed, 0 skipped, 0 failed, 10.67s**; [log](evidence/landing-final-pytest.log).
These eight are repeats, not eight additional distinct passing tests. The primary
landing captures below and motion recording were regenerated by this final run.
Compatibility captures/PDF came from the complete run before those final desktop
cosmetic adjustments; downstream layouts were unchanged throughout.

The updated supplemental evidence helper also completed successfully with the
same evidence-directory override: [log](evidence/metadata-check.log). It verifies
reduced motion and the synthetic PDF's snapshot/run/model identity; all three PDF
pages were regenerated in the compatibility directory. It did not change the
historical next-phase evidence.

Earlier development executions are not represented as final acceptance. The first
application/browser run overlapped edits and was **not a clean baseline**: 224
passed, 3 failed, 2 skipped. The three failures caught a decorative arrow entering
exact button text; the arrow is now CSS decoration with unchanged text/accessibility
name. The first new landing run had 2 passed / 5 failed and caught off-canvas light
geometry causing horizontal overflow. Its regression assertions were retained;
only decorative horizontal overflow is now contained. Subsequent visual iterations
and targeted runs passed before the complete run above.

## Fresh browser evidence

| Required viewport | Viewport capture | Full page |
| --- | --- | --- |
| 1440 × 900 | [Desktop](evidence/landing-1440.png) | [Full](evidence/landing-1440-full.png) |
| 768 × 1024 | [Tablet](evidence/landing-768.png) | [Full](evidence/landing-768-full.png) |
| 390 × 844 | [Mobile](evidence/landing-390.png) | [Full](evidence/landing-390-full.png) |

All three test the loaded artwork, both accessible action names, horizontal
containment, no page errors, local-only resource requests, and the examination
limitation fitting within the first viewport. Tablet/mobile additionally assert
headline → artwork → explanatory copy ordering.

- [Normal-motion recording](evidence/landing-normal-motion.webm): local desktop
  entrance, hover and keyboard-focus-preserving navigation into the existing
  dossier. Finite artwork animation reaches `finished`, iteration count **1**.
  Early/settled captures and sampled video frames were inspected. This is not a
  frame-time/performance benchmark or a claim of physical-device smoothness.
- [Keyboard focus](evidence/landing-keyboard-focus.png): real Tab order from skip
  link → brand → primary action; visible outline; Enter focuses the existing
  question field. Failed-art sample flow also uses keyboard activation.
- [Failed-art fallback](evidence/landing-390-fallback.png): abort both responsive
  image candidates, show inline SVG, retain layout and complete synthetic sample
  flow. No extra request is needed for the fallback.
- [Enlarged text](evidence/landing-390-large-text.png): doubled display/body/limitation
  text expands vertically without horizontal overflow. This is a targeted text
  scaling surrogate, not verification of every browser's native 200% zoom mode.
- Reduced-motion computed styles: artwork, heading and invitation animation names
  are `none`; root scroll behavior is `auto`. Supplemental helper confirms the
  existing analysis scan remains hidden with reduced motion.
- [Contrast](evidence/landing-contrast.json): minimum **5.8683:1** across eight
  selected desktop text/CTA samples, measured against composited screenshot
  backgrounds with text ink hidden. Includes light fields and the CTA gradient.
  This exceeds 4.5:1 in that scope; not a comprehensive accessibility audit.
- Existing browser suites cover create/sample/resume, saved dossier edits, upload
  rejection/duplicates/retry, uncertain creation, processing failure, source/report
  display, urgent/review restrictions, stale printing refusal, untrusted text,
  audience switching and print output at 390/768/1440.

## Source and repository checks

- `node --check frontend/landing.js`: passed.
- `node --check tools/artwork/render_tooth.js`: passed.
- `git diff --check`: passed.
- Backend, `frontend/app.js`, original `frontend/tooth.svg`, dependency manifests,
  and historical next-phase evidence have no changes.
- Workspace/Analysis/Results/footer DOM from the workspace section onward is
  byte-identical to HEAD. Home header styles are conditional on the active home
  view. No downstream stage was redesigned.
- Explicit new/changed visual-source checks found no credential-pattern matches
  and no remote frontend resources. The SVG namespace URI is not a network fetch.
- [Source checks and final hashes](evidence/source-checks.json) document exact scope.
  No ZIP content or credential/environment file was inspected.

## Visual self-review against landing reference

**Material improvement:** the flat outlined emblem is replaced with an original
continuous three-dimensional form, with softened crown transitions, tapered roots,
pearl shading, restrained rim light and faint reflection. The neutral charcoal
scene, larger editorial title, restrained secondary action and single background
light field give the landing a more coherent hierarchy. The feature-grid/ruled-row
structure is removed. Mobile presents the tooth before the explanation/actions,
with both actions and the limitation readable in the first specified viewport.

**Remaining limitations:** the tooth is a stylized local render, not photorealistic
natural enamel. It lacks the reference's fine surface structure, sophisticated
translucency and jewel-like optical detail; highlights still read as satin rather
than rich enamel. The environment is deliberately quieter and less richly lit.
Desktop still uses a clear RTL reading region to the right of the tooth; this is
not a replica of the reference's large immersive stage. Typography has stronger
hierarchy but remains system Tahoma/Segoe UI/DejaVu, not a dedicated Persian display
face. The static fallback has materially simpler form. These limitations remain
documented for future visual work; they do not revoke the recorded manual acceptance.

**NOT VERIFIED:** other browser engines; physical mobile
hardware; screen-reader behavior; comprehensive contrast/state coverage; native
zoom across engines; low-end-device performance; typography with every fallback
font. PostgreSQL/Docker/deployment/live-provider/clinical acceptance was not rerun
or undertaken in this frontend-only gate. No claim extends to those areas.

Stop here. No commit, push, PR update, merge, deployment or next-stage redesign.
