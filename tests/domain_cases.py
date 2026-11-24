from app.catalog import SPEC
from app.domain.calculate import calculate_rows
from app.domain.decision import decide_rows
from app.domain.prepare import prepare_rows
from app.intake.service import load

CLEAN = [{'work_order': 'WO1',
  'stage_seq': '1',
  'stage': '冲压',
  'input_qty': '1000',
  'good_qty': '950',
  'scrap_qty': '30',
  'rework_qty': '20',
  'rework_good': '10',
  'row_id': 'R001'},
 {'work_order': 'WO1',
  'stage_seq': '2',
  'stage': '焊接',
  'input_qty': '960',
  'good_qty': '912',
  'scrap_qty': '28',
  'rework_qty': '20',
  'rework_good': '10',
  'row_id': 'R002'},
 {'work_order': 'WO2',
  'stage_seq': '1',
  'stage': '冲压',
  'input_qty': '500',
  'good_qty': '490',
  'scrap_qty': '5',
  'rework_qty': '5',
  'rework_good': '4',
  'row_id': 'R003'},
 {'work_order': 'WO2',
  'stage_seq': '2',
  'stage': '焊接',
  'input_qty': '494',
  'good_qty': '470',
  'scrap_qty': '14',
  'rework_qty': '10',
  'rework_good': '8',
  'row_id': 'R004'}]


def row(**changes):
    item = dict(CLEAN[0])
    item.update(changes)
    return item


def calc(rows):
    items, issues = prepare_rows(rows)
    return calculate_rows(items), issues


def run(rows):
    items, issues = prepare_rows(rows)
    return decide_rows(calculate_rows(items)), issues


def run_profile(profile):
    return run(load(profile)["rows"])
