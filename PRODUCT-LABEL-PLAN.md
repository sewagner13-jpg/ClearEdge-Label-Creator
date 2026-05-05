# Product Label Plan

## Runtime Direction

- Use OpenAI for SDS/TDS extraction into the strict label schema.
- Keep the browser upload flow as the primary operator workflow.
- Store generated label artifacts in the configured application data directory.
- Deploy backend on Railway and frontend on Netlify.

## API Surface

- `POST /api/v1/labels/generate`
- `GET /api/v1/labels/{label_id}`
- `GET /api/v1/labels/{label_id}/download`
- `POST /api/v1/labels/{label_id}/override-approval`

## Quality Gates

- Schema validation before rendering.
- Compliance validation before download.
- Override workflow requires approver and reason.
- Unit and API contract tests must pass before deployment.
