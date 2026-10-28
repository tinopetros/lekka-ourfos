"""Firestore, in memory: as much of it as the API's tests need."""

from datetime import UTC, datetime

from google.cloud.firestore import SERVER_TIMESTAMP


class Snap:
    def __init__(self, data, id=None):
        self.data, self.id = data, id

    @property
    def exists(self):
        return self.data is not None

    def to_dict(self):
        return None if self.data is None else dict(self.data)


class Ref:
    def __init__(self, db, path):
        self.db, self.path = db, path
        self.id = path[-1]

    def get(self, transaction=None):
        return Snap(self.db.docs.get(self.path))

    def set(self, data, merge=False):
        # The server's time, as the server would set it
        data = {k: datetime.now(UTC) if v is SERVER_TIMESTAMP else v for k, v in data.items()}
        self.db.docs[self.path] = (self.db.docs.get(self.path, {}) if merge else {}) | data

    def collection(self, name):
        return Collection(self.db, "/".join(map(str, self.path)) + "/" + name)

    def delete(self):
        self.db.docs.pop(self.path, None)


class Collection:
    def __init__(self, db, name):
        self.db, self.name, self.field, self.descending, self.n, self.filters = db, name, None, False, None, []

    def document(self, id):
        return Ref(self.db, (self.name, id))

    def order_by(self, field, direction):
        self.field, self.descending = field, direction == "DESCENDING"
        return self

    def where(self, filter):
        self.filters.append((filter.field_path, filter.value))
        return self

    def stream(self):
        for (c, id), d in list(self.db.docs.items()):
            if c == self.name and all(d.get(f) == v for f, v in self.filters):
                yield Snap(d, id)

    def limit(self, n):
        self.n = n
        return self

    def get(self, transaction=None):
        docs = [d for (c, _), d in self.db.docs.items() if c == self.name and self.field in d]
        docs.sort(key=lambda d: d[self.field], reverse=self.descending)
        return [Snap(d) for d in docs[: self.n]]


class Transaction:
    def set(self, ref, data):
        ref.set(data)


class Db:
    def __init__(self):
        self.docs = {}

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return Transaction()

    def get_all(self, refs):
        return [r.get() for r in refs]
