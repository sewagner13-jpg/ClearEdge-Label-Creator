import pytest

from app.label_pipeline import infer_container_type_from_fill_amount


@pytest.mark.parametrize(
    ("fill_amount", "expected"),
    [
        ("55 lb", "pail"),
        ("55", "pail"),
        ("60 lb", None),
        ("60.1 lb", "drum"),
        ("441 lb", "drum"),
        ("2500 lb", "tote"),
        ("1000 kg", "tote"),
        ("24 kg", "pail"),
        ("unknown", None),
    ],
)
def test_infer_container_type_from_fill_amount(fill_amount, expected):
    assert infer_container_type_from_fill_amount(fill_amount) == expected
