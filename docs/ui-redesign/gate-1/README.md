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

# Current desktop reference match — 2026-10-02

Owner approved replacing the old hero wording with the exact aqua reference
wording and adding a future-login placeholder. This is the **actual local website
implementation**, not a flattened image or mockup. Earlier handoffs below are
history; their counts/visual acceptance do not describe this latest pass.

- HTML hero: `همراه هوشمند` / `سلامت دندان شما`, reference description and
  functional home/about/how/FAQ anchors. Header uses DANDOONJAN on home while
  retaining Persian branding downstream. Future login is a native disabled
  button, labelled as coming later; no JavaScript/API/authentication exists.
- Landing CSS: light continuous aqua lighting on `#9ED7E0`, no dark half-page
  field; 62px/650 two-line heading; existing tooth/circle geometry, reflection,
  pill dimensions and four truthful feature groups. Explicit glyph-local soft
  teal shadows support readable light text without darkening the environment.
- The synthetic sample note explicitly states that this offline demo does not
  actually interpret images. Existing examination/diagnosis limitation remains.
  Real create/sample/resume handlers and provider behavior are unchanged.
- Landing browser tests cover the new copy/header, inactive placeholder, geometry
  and actual rendered text backdrops. `test_p1_browser.py` updates only the former
  headline expectation to the newly approved wording.
- Existing editorial content stays below the feature row, followed by three
  truthful FAQ disclosures. No login backend, speed/security claim, new clinical
  capability, remote font or production/reference bitmap was added.

Current evidence: [1440 screenshot](evidence/reference-match/approved-copy-pass/landing-1440.png),
[full page](evidence/reference-match/approved-copy-pass/landing-1440-full.png),
[verification](VERIFICATION.md). **10 desktop/offline checks passed**.

Desktop only. No tablet/mobile adaptation or acceptance in this pass. No commit,
push, deployment, live/provider/external request or credential access. Owner
visual review is pending. HEAD remains `7ef5dfafa440d2603d1b9c4ff9f29fcb2b5633d8`.

---

## Earlier local handoffs

# Aqua landing implementation — owner review, 2026-10-01

This section is the current local handoff. The earlier charcoal/hero-tooth.png
implementation notes below remain historical; their visual acceptance does not
apply to this new aqua implementation. Owner review of the new captures is pending.

Scope: Landing only, following the owner's approved aqua plan and supplied
`frontend/hero-tooth-aqua.png`. Starting/current HEAD:
`7ef5dfafa440d2603d1b9c4ff9f29fcb2b5633d8`. No commit, push, PR modification,
deployment, paid service, real credential access, or live provider request.

## Current implementation

- `frontend/index.html`: only theme colour and hero image source/intrinsic dimensions
  change. All Persian editorial copy, limitations, synthetic sample notice and
  create/sample/resume IDs remain. Downstream DOM is identical to HEAD.
- `frontend/landing.css`: exact `#9ED7E0` home background; approved aqua tokens;
  large transparent tooth on the left, RTL copy on the right; CSS curved ring,
  floor shadow, restrained translucent header and soft light field behind text.
  Tablet/mobile recompose vertically; mobile image box is 250px tall, horizontal
  padding is 20px and both buttons span the available width. Lower editorial
  content and footer continue the aqua composition without card grids.
- `frontend/hero-tooth-aqua.png`: owner-supplied, previously untracked asset, used
  directly without rewriting/cropping/resampling. PNG, 1175 × 1338, RGBA, alpha
  extrema 0–255. SHA-256:
  `75ffebd1d2a64b1a330e25d2f38c3ae3a74060b67d843104079462c7dcb77447`.
- `verification/test_landing_browser.py`: approved asset/alpha, exact home base,
  composition/order, mobile image/CTA sizes, no overflow, image-error fallback,
  keyboard/reduced motion, enlarged text, home header isolation, and rendered
  contrast across all three widths. New screenshots/evidence stay in
  `evidence/aqua-landing/`.
- `verification/test_next_phase_browser.py`: with explicit owner steering, update
  the older palette assertion to use the shared rendered-pixel contrast check at
  all three widths. Keep the 4.5:1 requirement and expand covered text/control
  samples; nothing is skipped or excluded in final acceptance.
- `docs/ui-redesign/gate-1/README.md` and `VERIFICATION.md`: current evidence and
  limitations, with useful earlier documentation preserved below.

`landing.js`, `app.js`, `styles.css`, backend/provider code, Build Case, Analysis
and Results remain unchanged. The ZIP, alternative WEBP images and `tools/` were
not opened or changed. No image-generation tool was used.

See [current verification](VERIFICATION.md) and review fresh captures:
[1440px](evidence/aqua-landing/landing-1440.png),
[768px](evidence/aqua-landing/landing-768.png),
[390px](evidence/aqua-landing/landing-390.png).

Stop with the local implementation and screenshots for owner review.

---

## Historical implementation handoff (2026-09-30)

# UI redesign — implementation gate 1

Scope: **visual foundation and Landing only**. Starting commit
`5262c3e82761e65acdad07f8fee1eeb2cd98f649`, branch
`agent/sadeghi-next-phase`. Local implementation and synthetic offline verification.
No commit, push, PR modification, merge, deployment, external asset acquisition,
paid service, credentials or patient data are authorized in this gate.

The approved visual audit in the owner session is the design specification. The
four reference PNGs remain art direction, never bitmap UI text or source assets.
Manual visual acceptance was granted by the user on 2026-09-30 for the current
Landing and `frontend/hero-tooth.png`; automated tests cannot establish it.

## Implementation map and boundaries

- `frontend/index.html`: replace only `#view-home` content; keep `start-case`,
  `start-sample`, `resume-case` and their accessible names. Load local landing CSS
  and a decorative image-error handler. Theme color follows neutral charcoal.
- `frontend/styles.css`: remove superseded home/hero/story/float rules and unused
  editorial decoration. Keep workspace, analysis, report and print rules.
- `frontend/landing.css`: new reusable scene tokens, scoped home composition,
  home-only header/footer treatment, finite entrance, responsive recomposition.
  The existing stages deliberately retain their current appearance in this gate.
- `frontend/landing.js`: only expose the inline static SVG if the hero image fails,
  including the cached-failure case. No request, case, or report state changes.
- `frontend/app.js` and existing `frontend/tooth.svg`: untouched. Dossier, Analysis,
  Results, backend, APIs, persistence and safety/provenance boundaries unchanged.
- Existing browser fixtures remain local SQLite/Mock. Explicitly disable the live
  provider in the fixture. Evidence tools accept `NEXT_PHASE_EVIDENCE` so this gate
  does not overwrite historical artifacts. Supplemental metadata uses the new
  landing artwork selector.

## Visual foundation

Neutral near-black environment, pearl type, restrained copper emphasis. A common
light field and a fine curved floor edge connect the tooth and Persian copy.
No feature cards, sidebar, or glass boxes are needed on this page. The lower
narrative is editorial prose instead of the old three ruled feature rows.

At 1440, the tooth occupies center-left with RTL copy to the right. At 768, the
headline, tooth and invitation form a centered narrative. At 390, the order is
header, headline, tooth, explanation, primary action, secondary sample action,
explicit synthetic-sample context, examination/diagnosis/prescription limitation.
The initial narrative is tested at the specified viewport heights, not by hiding
content to force a screenshot fit. Enlarged text can grow the page vertically.

Primary CTA text and both existing action handlers are retained. The secondary
action uses understated underlining rather than another large filled button.
The visible limitation states that this explains evidence and supports discussion,
not examination, diagnosis or prescription.

Motion consists of finite 650–850ms opacity/translation reveals and short control
feedback. No recurring float, parallax, scroll hijack, or runtime renderer. Reduced
motion removes animation/transitions and preserves global instant scrolling.

## Original tooth and provenance

The primary tooth is an original local procedural 3D study exported to static
responsive WebP images. `tools/artwork/render_tooth.js` defines the continuous
crown, shallow cusp relief, tapered rounded roots, pearl material, studio lights
and subtle rim. An offline Canvas2D CPU sphere tracer produces pixels;
`tools/artwork/render_tooth.py` uses the already installed Chrome/Pillow tools to
export the images and a faint reflection. It blocks network requests. Neither
renderer nor Canvas is included in the product runtime.

No model, texture, stock image, radiograph, reference-image pixels or external
asset were imported. This is artistic geometry, not a validated anatomical model,
clinical finding, patient-specific tooth, or diagnostic visualization. The inline
SVG alternative is intentionally simpler and requires no separate asset request.

Reproduce locally with the existing verification environment:

```text
.venv/Scripts/python.exe tools/artwork/render_tooth.py
```

The first vector prototype was rejected during self-review because its crown
looked segmented. The CPU render was iterated to improve continuity, roots,
lighting and material. This is a stylized enamel study; photorealism, fine enamel
microstructure and reference-level material fidelity are not claimed.

## Typography provenance

No font was downloaded or copied. No bundled font exists in the frontend.
Inspection found system DejaVu (local Bitstream/DejaVu license inspected) and
Windows Tahoma/Arabic Typesetting. Windows font files were not redistributed.
This gate uses `Tahoma, Segoe UI, DejaVu Sans, sans-serif` from the user's system.
Display uses normal Persian tracking, 88/64/44px starting sizes and explicit
hierarchy. A dedicated licensed Persian editorial face remains an unresolved
visual dependency; fallback appearance varies across operating systems.

## Verification and manual review

Final exact results and limitations are recorded in `VERIFICATION.md`. Screenshots,
normal-motion recording, contrast measurements and test logs live in `evidence/`.
These are new captures of this implementation. Historical next-phase acceptance
artifacts are preserved. No existing functional test result is presented as visual
acceptance. Stop after reporting this gate; do not propagate the redesign or commit.
