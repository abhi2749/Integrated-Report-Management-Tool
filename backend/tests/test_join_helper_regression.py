import database


def test_join_streaming_helpers_remain_available():
    assert callable(database._join_stream)
    assert callable(database._project_join_stream)


def test_project_join_stream_is_lazy_and_honors_limit():
    rows = ({"left.id": value} for value in range(1000000))
    projected, selected = database._project_join_stream(rows, [{"field": "left.id", "alias": "id"}], limit=1)
    assert selected == ["left.id"]
    assert list(projected) == [{"id": 0}]
