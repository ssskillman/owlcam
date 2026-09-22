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


def test_visit_store_counts_recent_captures(tmp_path):
    store = VisitStore(tmp_path / "visits.sqlite", tmp_path / "thumbs")
    store.add(
        species="barred owl",
        category="bird",
        confidence=0.9,
        is_unknown=False,
        model_version="test",
        source="feed_watcher",
        thumbnail=b"jpeg",
    )
    store.add(
        species="cow",
        category="mammal",
        confidence=0.62,
        is_unknown=False,
        model_version="test",
        source="browser",
        thumbnail=b"jpeg",
    )
    assert store.count_since_hours(24, source="feed_watcher") == 1
    assert store.count_since_hours(24, source=None) == 2


def test_visit_store_calendar_and_day_activity(tmp_path):
    store = VisitStore(tmp_path / "visits.sqlite", tmp_path / "thumbs")
    first = store.add(
        species="barred owl",
        category="bird",
        confidence=0.9,
        is_unknown=False,
        model_version="test",
        source="feed_watcher",
        thumbnail=b"jpeg",
    )
    second = store.add(
        species="cow",
        category="mammal",
        confidence=0.62,
        is_unknown=False,
        model_version="test",
        source="feed_watcher",
        thumbnail=b"jpeg",
    )
    assert first and second
    row = store.get_visit(first)
    month = int(row.created_at[5:7])
    year = int(row.created_at[:4])
    days = store.month_calendar(year, month, source="feed_watcher")
    assert len(days) == 1
    assert days[0]["visits"] == 2
    assert days[0]["pics"] == 2
    assert days[0]["entrances"] == 2
    events = store.day_activity(row.created_at[:10], source="feed_watcher")
    assert any(event["kind"] == "entrance" for event in events)
    assert any(event["kind"] == "pic" for event in events)


def test_visit_store_delete_removes_row_and_thumbnail(tmp_path):
    store = VisitStore(tmp_path / "visits.sqlite", tmp_path / "thumbs")
    visit_id = store.add(
        species="cow",
        category="mammal",
        confidence=0.62,
        is_unknown=False,
        model_version="test",
        source="feed_watcher",
        thumbnail=b"jpeg",
    )
    row = store.get_visit(visit_id)
    thumb_path = store.thumbnail_path(row.thumbnail_name)
    assert thumb_path.is_file()
    assert store.delete_visit(visit_id)
    assert store.get_visit(visit_id) is None
    assert not thumb_path.is_file()
    assert not store.delete_visit(visit_id)


def test_alert_cooldown_blocks_repeat(tmp_path):
    cooldowns = AlertCooldownStore(tmp_path / "alerts.sqlite")
    assert cooldowns.may_send("raccoon", 1800)
    cooldowns.mark_sent("raccoon")
    assert not cooldowns.may_send("raccoon", 1800)
