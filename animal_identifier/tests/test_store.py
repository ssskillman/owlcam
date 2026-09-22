from animal_identifier.store import AlertCooldownStore, IdentificationStore, VisitStore


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


def test_visit_store_lists_and_thumbnails(tmp_path):
    store = VisitStore(tmp_path / "visits.sqlite", tmp_path / "thumbs")
    visit_id = store.add(
        species="barred owl",
        category="bird",
        confidence=0.9,
        is_unknown=False,
        model_version="test",
        source="feed_watcher",
        thumbnail=b"jpeg",
    )
    assert visit_id == 1
    rows = store.list_visits(limit=10)
    assert rows[0].species == "barred owl"
    assert store.thumbnail_path(rows[0].thumbnail_name).read_bytes() == b"jpeg"


def test_alert_cooldown_blocks_repeat(tmp_path):
    cooldowns = AlertCooldownStore(tmp_path / "alerts.sqlite")
    assert cooldowns.may_send("raccoon", 1800)
    cooldowns.mark_sent("raccoon")
    assert not cooldowns.may_send("raccoon", 1800)
