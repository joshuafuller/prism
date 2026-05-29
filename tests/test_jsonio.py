from prism.jsonio import extract_json_array, extract_json_object, strip_code_fence


def test_strip_code_fence_removes_fences() -> None:
    assert strip_code_fence("```json\n[]\n```") == "[]"


def test_extract_json_array_from_surrounding_prose() -> None:
    text = 'Sure, here are the findings:\n[{"id": "1"}]\nLet me know!'
    assert extract_json_array(text) == '[{"id": "1"}]'


def test_extract_json_array_none_when_absent() -> None:
    assert extract_json_array("no array in here") is None


def test_extract_json_object_from_surrounding_prose() -> None:
    text = 'My verdict:\n{"decision": "approved"}\nDone.'
    assert extract_json_object(text) == '{"decision": "approved"}'


def test_extract_json_object_none_when_absent() -> None:
    assert extract_json_object("nothing here") is None
