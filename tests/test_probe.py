from scripts.probe import describe_shape


def test_shape_shows_keys_and_types_never_values() -> None:
    payload = [{"id": 1, "email": "secret@example.test", "company": {"name": "Acme"}, "tags": []}]

    shape = describe_shape(payload)

    assert shape == "list[1] of {id: int, email: str, company: {name: str}, tags: list[0]}"
    assert "secret@example.test" not in shape
    assert "Acme" not in shape


def test_shape_depth_is_limited() -> None:
    assert describe_shape({"a": {"b": {"c": {"d": {"e": 1}}}}}) == "{a: {b: {c: {d: …}}}}"
