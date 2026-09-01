# T0006 - SilaPox Label And DOT Sheet Completeness

## User-Observable Outcome
The SilaPox product label prints every source-backed GHS hazard and precautionary statement without an NFPA diamond, while page 2 contains one large Class 9 hazard label and one large marine-pollutant mark on the same printable sheet.

## Root Cause
- Section 14 extraction correctly returns `transport.marine_pollutant=true`.
- `build_dot_shipping_review()` adds only hazard classes to `required_stickers`; the marine-pollutant value becomes a review action but not a rendered mark.
- The current renderer repeats requested hazard labels to fill four 100 mm positions, so the omitted marine mark appears as four Class 9 copies.
- The horizontal shipped-label fitter eventually selects an empty H/P statement fallback when the fixed NFPA/symbol/product-use/DOT layout exceeds the footer limit, even though extraction contains all source statements.

## Scope
- Add the official marine-pollutant mark from 49 CFR 172.322 as an approved repository asset with source provenance.
- Add the mark to `required_stickers` whenever a regulated shipped/DOT label has `marine_pollutant=true`.
- Render the Class 9 plus marine-pollutant pair once each at 120 mm on a landscape US Letter sheet.
- Preserve the existing 100 mm four-up layout for sheets that do not contain the marine-pollutant pair.
- Keep the product label as page 1 and the combined DOT labels/marks sheet as page 2 in preview and PDF.
- Remove NFPA 704 from product-label rendering; NFPA is not a required GHS shipped-container label element.
- Render all extracted H/P statements in a two-column safety section and compact the horizontal DOT summary so the text remains inside the label frame.

## Regulatory Basis
- 49 CFR 172.407(c): hazard labels are at least 100 mm per side.
- 49 CFR 172.322(e): the marine-pollutant mark is square-on-point, black on white/contrasting background, with a border at least 2 mm; applicable non-bulk and sub-1,000-gallon bulk marks are at least 100 mm per side.
- Class 9 package graphics are labels/marks, not domestic Class 9 placards; 49 CFR 172.504(f)(9) provides the domestic Class 9 placarding exception.

## Non-Goals
- Do not change SDS extraction, Class 9 classification, label dimensions, or approved GHS artwork.
- Do not dynamically invent DOT artwork.
- Do not represent the page-2 graphics as vehicle placards.

## Deployment
Deployment is in scope under the standing deploy-after-change instruction. Use only `scripts/release.sh --deploy` after all gates pass.

## Acceptance Tests
- SilaPox-like `UN3082`, Class 9, Packing Group III, `marine_pollutant=true` returns required asset keys `9` and `marine_pollutant`.
- Page 2 contains exactly one of each mark, not four Class 9 copies.
- Both graphics are 120 mm square and the page is US Letter landscape.
- The separate DOT PDF and full label PDF contain the same page-2 output.
- A Class 9 label with `marine_pollutant=false` preserves the existing non-marine layout.
- The SilaPox fixture renders all 8 H-statements and all 21 P-statements with no ellipsis and no `nfpa-704` element.
- Colonless and wrapped SDS codes, combined P-codes, and the source typo `Precationary Statements` are parsed without dropping or contaminating statements.
- The horizontal DOT and safety panels remain above the footer with no overlap.

## Status
In progress.
