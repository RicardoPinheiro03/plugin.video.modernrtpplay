from rtpplay import Cache


def test_values_round_trip_as_json(clock):
    cache = Cache(clock=clock)
    cache.set("k", {"a": [1, 2]}, ttl=60)
    assert cache.get("k") == {"a": [1, 2]}
    assert cache.get("missing") is None
    cache.close()


def test_values_expire(clock):
    cache = Cache(clock=clock)
    cache.set("k", 1, ttl=60)
    clock.now += 59
    assert cache.get("k") == 1
    clock.now += 1
    assert cache.get("k") is None
    cache.close()


def test_file_cache_is_shared_and_pruned_on_open(tmp_path, clock):
    path = str(tmp_path / "cache.db")
    first = Cache(path, clock=clock)
    first.set("old", 1, ttl=10)
    first.set("new", 2, ttl=100)
    first.close()
    clock.now += 50
    second = Cache(path, clock=clock)
    assert second.get("new") == 2
    assert second._db.execute("SELECT key FROM cache").fetchall() == [("new",)]
    second.close()


def test_a_broken_cache_reads_as_empty_and_ignores_writes(clock):
    cache = Cache(clock=clock)
    cache.close()  # every query now raises sqlite3.ProgrammingError
    cache.set("k", 1, ttl=60)
    assert cache.get("k") is None
