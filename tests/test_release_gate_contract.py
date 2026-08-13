from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_SCRIPT = REPO_ROOT / "scripts" / "release.sh"


def test_release_gate_orders_verification_before_push_and_live_smoke():
    script = RELEASE_SCRIPT.read_text()

    test_position = script.index('"$PYTHON_BIN" -m pytest -q')
    parity_position = script.index('log "Starting local Railway-parity server"')
    push_position = script.index('git push origin "HEAD:${PRODUCTION_BRANCH}"')
    deployed_commit_position = script.index('if [[ "$LIVE_SHA" == "$COMMIT_SHA" ]]')
    live_generation_position = script.index('log "Running live Edgemer SDS/TDS generation smoke"')

    assert test_position < parity_position < push_position
    assert push_position < deployed_commit_position < live_generation_position


def test_release_gate_requires_clean_tree_real_documents_and_artifact_validation():
    script = RELEASE_SCRIPT.read_text()

    assert '[[ -z "$(git status --porcelain)" ]]' in script
    assert '[[ -f "$SDS_FILE" ]]' in script
    assert '[[ -f "$TDS_FILE" ]]' in script
    assert 'ET.fromstring(svg_path.read_bytes())' in script
    assert 'startswith(b"%PDF")' in script


def test_ci_loads_the_built_docker_image_before_running_it():
    workflow = (REPO_ROOT / ".github" / "workflows" / "test.yml").read_text()

    build_step = workflow.split("- name: Build Docker image", 1)[1]
    build_step = build_step.split("- name: Test Docker image", 1)[0]

    assert "load: true" in build_step
