from animal_identifier.store import IdentificationStore


def test_identification_summary_groups_categories_and_species(tmp_path):
    store = IdentificationStore(tmp_path / "identifications.sqlite")
    store.add_many(
        [
            ("barred owl", "bird", "test-model"),
            ("barred owl", "bird", "test-model"),
            ("great horned owl", "bird", "test-model"),
            ("copperhead", "reptile", "test-model"),
        ]
    )

    assert store.summary() == {
        "total": 4,
        "categories": [
            {
                "category": "bird",
                "count": 3,
                "species": [
                    {"species": "barred owl", "count": 2},
                    {"species": "great horned owl", "count": 1},
                ],
            },
            {
                "category": "reptile",
                "count": 1,
                "species": [{"species": "copperhead", "count": 1}],
            },
        ],
    }


def test_identification_summary_is_empty_before_any_known_results(tmp_path):
    store = IdentificationStore(tmp_path / "identifications.sqlite")

    assert store.summary() == {"total": 0, "categories": []}
