from app.label_stub import LabelGenerator


def test_template_registry_has_phase2_templates():
    generator = LabelGenerator()
    assert "clearedge_pail_v1" in generator.templates
    assert "clearedge_drum_v1" in generator.templates


def test_get_template_config_by_size_and_id():
    generator = LabelGenerator()
    by_size = generator.get_template_config(None, "drum")
    by_id = generator.get_template_config("clearedge_pail_v1", "drum")

    assert by_size["size"] == "drum"
    assert by_id["size"] == "pail"


def test_fit_text_truncates_deterministically():
    text = "This is a very long product name that should be truncated"
    fitted = LabelGenerator._fit_text(text, 20)
    assert fitted.endswith("...")
    assert len(fitted) <= 20


def test_template_brand_tokens_present():
    generator = LabelGenerator()
    cfg = generator.get_template_config("clearedge_pail_v1", "pail")
    assert cfg["brand"]["header_color"].startswith("#")
    assert cfg["brand"]["accent_color"].startswith("#")
    assert cfg["brand"]["text_color"].startswith("#")


def test_wrap_lines_and_format_statements_clips_deterministically():
    generator = LabelGenerator()
    long_text = "This precautionary statement should wrap cleanly and clip at predictable boundaries for stable print output"
    wrapped = generator._wrap_lines(long_text, line_width=30, max_lines=2)
    assert len(wrapped) <= 2
    assert wrapped[-1].endswith("...")

    class Statement:
        def __init__(self, code, text):
            self.code = code
            self.text = text

    statements = [Statement("P101", long_text)]
    formatted = generator._format_statements(statements, line_width=30, max_items=1)
    assert formatted[0]["code"] == "P101"
    assert formatted[0]["text"].endswith("...")
