from aracgen import snapshot as module
from aracgen.capital_trainer_catalog import CAPITAL_ZONES
from aracgen.snapshot_model import ColumnDef, TableSchema


def test_capital_menus_are_captured_before_cursor_closes(monkeypatch):
    class Cursor:
        closed = False
        query = ""

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.closed = True

        def execute(self, query, *_):
            assert not self.closed
            self.query = query

        def fetchall(self):
            if "SELECT c.guid" in self.query:
                return [dict(guid=1, entry=1, map=0, position_x=0, position_y=0,
                             position_z=0, orientation=0, equipment_id=0,
                             curhealth=1, curmana=0, npcflag=0)]
            return []

    cursor = Cursor()

    class Connection:
        def cursor(self):
            return cursor

    def capture_menus(active_cursor):
        assert not active_cursor.closed
        return [{"menu_id": 42}]

    monkeypatch.setattr(module, "_load_playercreateinfo", lambda _: [])
    monkeypatch.setattr(module, "starter_zone_sql_clause", lambda _: ("1=1", []))
    monkeypatch.setattr(module, "_capture_capital_trainers", lambda *_: [])
    monkeypatch.setattr(module, "_capture_capital_class_menus", capture_menus)
    schema = TableSchema("creature", (ColumnDef("id", 1, "int", False, 0),))
    result = module.capture_trainer_data(Connection(), schema)
    assert result["capital_class_menus"] == [{"menu_id": 42}]
    assert cursor.closed


def test_poi_capital_classification_uses_distinct_maps():
    for zone in CAPITAL_ZONES:
        assert module._classify_poi_capital(zone.cx, zone.cy) == zone.label
    assert module._classify_poi_capital(0, 0) is None
