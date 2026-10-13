from src.retrieval.retrieve import RetrievalQuery, build_where


def _query(**overrides):
    base = {
        "text": "plazo",
        "signing_date_i": 20231230,
        "contract_type": "locacion",
        "regime": "DNU 70/2023",
        "k": 5,
    }
    base.update(overrides)
    return RetrievalQuery(**base)


def test_where_restricts_jurisdictions_and_period():
    where = build_where(_query())
    conditions = where["$and"]
    assert {"jurisdiction": {"$in": ["nacional", "CABA"]}} in conditions
    assert {"valid_from_i": {"$lte": 20231230}} in conditions
    assert {"valid_to_i": {"$gte": 20231230}} in conditions


def test_where_filters_contract_type_and_allows_all():
    conditions = build_where(_query())["$and"]
    assert {"contract_type": {"$in": ["locacion", "all"]}} in conditions


def test_regime_filter_applies_to_national_only():
    conditions = build_where(_query())["$and"]
    assert {"$or": [{"jurisdiction": "CABA"}, {"regime": "DNU 70/2023"}]} in conditions


def test_no_regime_means_no_regime_filter():
    conditions = build_where(_query(regime=None))["$and"]
    assert not any("$or" in c for c in conditions)
