import json
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_node_module(script: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_result_view_model_maps_preview_pages_downloads_and_canva_handoff():
    script = textwrap.dedent(
        """
        import { createResultViewModel } from './netlify-frontend/js/view-model.js';

        const model = createResultViewModel({
          label_id: 'label_test_123',
          status: 'ready',
          preview: {
            page_count: 2,
            pages: [
              { page_number: 1, label: 'Product label', url: '/api/v1/labels/label_test_123/preview.svg' },
              { page_number: 2, label: 'DOT sticker sheet', url: '/api/v1/labels/label_test_123/dot-stickers/preview-page-1.svg' }
            ]
          },
          download: { available: true, url: '/api/v1/labels/label_test_123/download', page_count: 2 },
          label: {
            download_url: '/api/v1/labels/label_test_123/download',
            dot_sticker_pdf_url: '/api/v1/labels/label_test_123/dot-stickers.pdf',
            canva_csv_url: '/api/v1/labels/label_test_123/canva-export.csv',
            canva_json_url: '/api/v1/labels/label_test_123/canva-export.json'
          },
          dot_stickers: { available: true, reason: null },
          validation: { errors: [], warnings: [] }
        });

        console.log(JSON.stringify({
          statusTone: model.statusTone,
          pageCount: model.pageCount,
          hasDotStickerPage: model.hasDotStickerPage,
          hasFullPdf: model.actions.hasFullPdf,
          hasDotStickerPdf: model.actions.hasDotStickerPdf,
          hasCanvaHandoff: model.actions.hasCanvaHandoff
        }));
        """
    )

    assert run_node_module(script) == {
        "statusTone": "ready",
        "pageCount": 2,
        "hasDotStickerPage": True,
        "hasFullPdf": True,
        "hasDotStickerPdf": True,
        "hasCanvaHandoff": True,
    }


def test_result_view_model_explains_missing_dot_sticker_page():
    script = textwrap.dedent(
        """
        import { createResultViewModel } from './netlify-frontend/js/view-model.js';

        const model = createResultViewModel({
          status: 'needs_review',
          preview: {
            page_count: 1,
            pages: [
              { page_number: 1, label: 'Product label', inline_svg: '<svg></svg>' }
            ]
          },
          label: {},
          download: { available: false, reason: 'Review required' },
          dot_stickers: {
            available: false,
            reason: 'DOT sticker sheet not generated - enter hazard class.'
          }
        });

        console.log(JSON.stringify({
          statusTone: model.statusTone,
          pageCount: model.pageCount,
          hasDotStickerPage: model.hasDotStickerPage,
          dotStickerReason: model.dotStickerReason
        }));
        """
    )

    assert run_node_module(script) == {
        "statusTone": "review",
        "pageCount": 1,
        "hasDotStickerPage": False,
        "dotStickerReason": "DOT sticker sheet not generated - enter hazard class.",
    }


def test_generation_requirements_identify_only_missing_weight():
    script = textwrap.dedent(
        """
        import { createGenerationRequirements } from './netlify-frontend/js/view-model.js';

        console.log(JSON.stringify(createGenerationRequirements({
          fileCount: 2,
          productName: 'SilaRes CE 618',
          fillAmount: '',
          sampleLabel: false
        })));
        """
    )

    assert run_node_module(script) == [{
        "field": "fillAmount",
        "label": "Net Weight / Fill Amount",
    }]


def test_dot_analysis_summary_makes_not_regulated_section_14_result_explicit():
    script = textwrap.dedent(
        """
        import { createDotAnalysisSummary } from './netlify-frontend/js/view-model.js';

        console.log(JSON.stringify(createDotAnalysisSummary({
          extracted: {
            transport: {
              not_regulated: true,
              proper_shipping_name: 'Not applicable'
            },
            evidence: [{
              field_path: 'transport.not_regulated',
              doc: 'SDS',
              section: 'Section 14',
              page: 7,
              quote: 'Not regulated as a dangerous good for transport.'
            }]
          }
        })));
        """
    )

    assert run_node_module(script) == {
        "status": "not_regulated",
        "tone": "ready",
        "title": "Section 14 parsed: Not regulated for DOT transport",
        "detail": "The uploaded SDS does not require UN/NA number, hazard class, or packing group for this transport state.",
        "fields": [],
        "missingFields": [],
        "evidence": "SDS, Section 14, page 7: Not regulated as a dangerous good for transport.",
    }


def test_dot_analysis_summary_lists_regulated_fields_and_missing_values():
    script = textwrap.dedent(
        """
        import { createDotAnalysisSummary } from './netlify-frontend/js/view-model.js';

        console.log(JSON.stringify(createDotAnalysisSummary({
          extracted: {
            transport: {
              not_regulated: false,
              un_number: 'UN1993',
              proper_shipping_name: 'Flammable liquids, n.o.s.',
              hazard_class: '3',
              packing_group: null
            },
            evidence: []
          }
        })));
        """
    )

    assert run_node_module(script) == {
        "status": "regulated",
        "tone": "review",
        "title": "Section 14 parsed: DOT regulated",
        "detail": "Review the parsed highway-shipping fields before generating the label.",
        "fields": [
            "UN/NA: UN1993",
            "Shipping name: Flammable liquids, n.o.s.",
            "Hazard class: 3",
        ],
        "missingFields": ["Packing group"],
        "evidence": "",
    }


def test_dot_analysis_summary_marks_missing_section_14_conclusion_for_review():
    script = textwrap.dedent(
        """
        import { createDotAnalysisSummary } from './netlify-frontend/js/view-model.js';

        console.log(JSON.stringify(createDotAnalysisSummary({
          extracted: { transport: {}, evidence: [] }
        })));
        """
    )

    assert run_node_module(script) == {
        "status": "undetermined",
        "tone": "blocked",
        "title": "Section 14 result needs review",
        "detail": "The SDS/TDS analysis did not find a reliable DOT regulated or not-regulated conclusion. Review Section 14 or enter the transport fields manually.",
        "fields": [],
        "missingFields": [],
        "evidence": "",
    }
