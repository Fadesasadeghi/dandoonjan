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
