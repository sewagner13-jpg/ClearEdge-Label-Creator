# T0007 - Two-Up DOT Sticker Sheets

## User-Observable Outcome
Every DOT sticker sheet contains exactly two maximum-size approved graphics: two copies when only one type is required, or one copy of each type when multiple types are required.

## Scope
- Use a fixed US Letter landscape, two-column, one-row layout.
- Render each DOT hazard label or package mark at 135 mm square.
- Deduplicate requested artwork by approved asset key.
- Duplicate a single required type so the sheet contains two copies.
- Preserve one copy of each type when multiple types are required.
- Paginate more than two unique types in stable order; duplicate an unpaired final type.
- Preserve approved DOT and marine-pollutant assets without modifying their artwork.
- Update API metadata and regression tests to report the new size and orientation.

## Non-Goals
- Do not change SDS/TDS extraction, DOT classification, label page 1, or approved artwork.
- Do not add unsupported DOT hazard classes.
- Do not call package labels or marks vehicle placards in product copy.

## Deployment
Deployment is in scope under the standing deploy-after-change instruction. Use only `scripts/release.sh --deploy` after all gates pass.

## Acceptance Tests
- One required Class 3 asset renders two Class 3 copies on one landscape sheet.
- Class 3 plus Class 8 renders one of each on one landscape sheet.
- Class 9 plus marine-pollutant renders one of each on one landscape sheet.
- Three unique assets render two landscape sheets; the unpaired final asset is duplicated.
- Every placement is 135 mm square.
- API metadata reports `sticker_size_mm=135` and `sheet_size=US Letter landscape`.
- The full label PDF appends the same sticker-sheet pages returned by the preview and separate DOT PDF.

## Status
In progress.
