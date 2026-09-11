from query_model import QueryDefinition


def test_canonical_query_defaults_are_stable():
    query = QueryDefinition()
    assert query.group_by == []
    assert query.calculations == []
    assert query.limit == 0
