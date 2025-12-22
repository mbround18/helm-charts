import charts.meilisearch.resources.main as prov


class DummyKey:
    def __init__(self, key, name=None, indexes=None, actions=None):
        self.key = key
        self.name = name
        self.description = name
        self.indexes = indexes or []
        self.actions = actions or []


class DummyClient:
    def __init__(self, keys=None, existing_indexes=None):
        self._keys = keys or []
        self._indexes = set(existing_indexes or [])

    def get_keys(self):
        # return as list
        return [
            {"key": k.key, "name": k.name, "indexes": k.indexes, "actions": k.actions}
            for k in self._keys
        ]

    @property
    def url(self):
        return "http://dummy"

    def get_index(self, uid):
        if uid not in self._indexes:
            raise Exception("not found")
        return {"uid": uid}

    def create_index(self, *args, **kwargs):
        # accept uid kw or first arg
        if "uid" in kwargs:
            uid = kwargs["uid"]
        elif args:
            uid = args[0]
        else:
            raise TypeError("missing uid")
        self._indexes.add(uid)
        return {"uid": uid}


def test_find_matching_key_by_description(monkeypatch):
    c = DummyClient(
        keys=[DummyKey("ABC123", name="my-key", indexes=["a"], actions=["* "])]
    )

    # patch validate_api_key to return True for this key
    monkeypatch.setattr(prov, "validate_api_key", lambda url, k: True)

    found = prov.find_matching_key(c, "http://dummy", "my-key", ["a"], ["read"])
    assert found == "ABC123"


def test_find_matching_key_by_superset(monkeypatch):
    c = DummyClient(
        keys=[
            DummyKey(
                "XYZ789", name="other", indexes=["a", "b"], actions=["read", "write"]
            )
        ]
    )
    monkeypatch.setattr(prov, "validate_api_key", lambda url, k: True)
    found = prov.find_matching_key(c, "http://dummy", "notfound", ["a"], ["read"])
    assert found == "XYZ789"


def test_ensure_indexes_creates_missing():
    c = DummyClient(existing_indexes=["a"])
    prov.ensure_indexes(c, ["a", "b"])  # should create b
    # client should now report index b exists
    assert "b" in c._indexes


def test_ensure_indexes_skip_wildcard(capfd):
    c = DummyClient()
    prov.ensure_indexes(c, ["*"])
    captured = capfd.readouterr()
    assert "Index creation skipped" in captured.out
