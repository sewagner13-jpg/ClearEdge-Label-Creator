import pytest

from app.salesperson_library import SalespersonLibrary


def test_salesperson_library_create_list_get_and_delete(tmp_path):
    library = SalespersonLibrary(tmp_path)

    created = library.create_salesperson(
        name="Sean Wagner",
        email="sean@clear-edge.net",
        phone="704-799-5769",
    )

    assert created["salesperson_id"].startswith("sales_")
    assert created["name"] == "Sean Wagner"
    assert library.get_salesperson(created["salesperson_id"]) == created
    assert library.list_salespeople() == [created]

    assert library.delete_salesperson(created["salesperson_id"]) is True
    assert library.list_salespeople() == []


def test_salesperson_library_rejects_blank_name_or_missing_contact(tmp_path):
    library = SalespersonLibrary(tmp_path)

    with pytest.raises(ValueError, match="SALESPERSON_NAME_REQUIRED"):
        library.create_salesperson(name="", email="sean@clear-edge.net", phone="")

    with pytest.raises(ValueError, match="SALESPERSON_CONTACT_REQUIRED"):
        library.create_salesperson(name="Sean Wagner", email="", phone="")


def test_salesperson_library_rejects_invalid_lookup_id(tmp_path):
    library = SalespersonLibrary(tmp_path)

    with pytest.raises(ValueError, match="SALESPERSON_NOT_FOUND"):
        library.get_salesperson("sales_missing")
