from app.review.store import Store


class ComparisonStore(Store):
    """SQLite store with run and comparison methods.

    The comparison table is created by :class:`Store`; this subclass gives
    callers a module path that matches the comparison feature.
    """

    def init_db(self):
        return self.init()

    def initialize(self):
        return self.init()


__all__ = ["ComparisonStore", "Store"]
