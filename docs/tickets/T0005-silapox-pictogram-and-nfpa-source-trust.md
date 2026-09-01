# T0005 - SilaPox Pictogram And NFPA Source Trust

## User-Observable Outcome
The operator can generate a SilaPox label whose GHS pictograms match the symbols embedded in SDS Section 2, while any NFPA `0-0-0` fallback is explicitly identified as a ClearEdge default rather than a sourced rating.

## Root Cause
- PDF text extraction cannot see embedded pictogram artwork. The deterministic fallback matches the combined headings `Skin Corrosion/Irritation` and `Serious Eye Damage/Eye Irritation` without checking Category 2, so it incorrectly adds `GHS05`.
- Source reconciliation unions deterministic and OpenAI pictogram lists, so an inferred pictogram is never removed when the SDS artwork shows a different authoritative set.
- Missing NFPA/HMIS values are defaulted to `0-0-0`, but the generated data does not carry explicit machine-readable provenance distinguishing that policy default from a sourced rating.

## Scope
- Detect embedded GHS pictograms in the SDS by matching them only against the approved assets in `app/assets/ghs_pictograms`.
- Treat confidently detected SDS pictograms as the authoritative set.
- Make text-only corrosion derivation category-aware: Category 2 skin/eye irritation must not produce `GHS05`.
- Replace conflicting AI pictograms when authoritative embedded SDS pictograms are present.
- Add explicit NFPA source metadata: `sds`, `hmis`, or `clearedge_default`.
- Preserve the settled `0-0-0` fallback and blank special-hazard quadrant when NFPA/HMIS is absent.

## Non-Goals
- Do not infer an NFPA number from GHS classifications.
- Do not change approved GHS artwork, DOT extraction, branding, label dimensions, or download behavior.
- Do not commit the complete uploaded supplier SDS. Use a bounded SilaPox-derived regression fixture and verify the original local SDS during the release check.

## Deployment
Deployment is in scope under the standing deploy-after-change instruction. Use only `scripts/release.sh --deploy` after the full verification gate passes.

## Acceptance Tests
- A SilaPox Section 2 fixture with embedded flame, exclamation, and health-hazard symbols returns exactly `GHS02`, `GHS07`, and `GHS08`.
- Category 2 `Skin Corrosion/Irritation` and Category 2 `Serious Eye Damage/Eye Irritation` do not add `GHS05`.
- An AI list containing `GHS05` is replaced by the authoritative embedded SDS list during reconciliation.
- Missing NFPA/HMIS returns `0-0-0` with source `clearedge_default` and a visible warning.
- Actual local `SDS_LYLC-405_Silicone Resin EF_LYSON.pdf` detects exactly the three Section 2 pictograms and no NFPA/HMIS evidence.

## Status
Complete.

## Verification
- `PYTHON_BIN=./.venv/bin/python ./scripts/release.sh --deploy --sds '/Users/seanwagner/Downloads/Edgemer E618_MSDS (1).pdf' --tds '/Users/seanwagner/Downloads/Edgemer E618 TDS (1).pdf'` passed for `d4bfd9d6d2dfe6da63bb0bd9b39b334e87aa8ec3` with 215 tests, 85% coverage, browser E2E, static checks, local Railway parity, and exact-commit production confirmation.
- Live SilaPox acceptance label: `label_CESilaPoxEF_bdd3bb8b`.
- Live API assertions: `pictograms=[GHS02,GHS07,GHS08]`, no `GHS05`, `signal_word=Warning`, and NFPA `0-0-0` with `source=clearedge_default`.
- Live preview assertions: approved flame, exclamation, and health-hazard assets present; corrosion absent; `SDS not listed; default 0` present.
