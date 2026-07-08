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
