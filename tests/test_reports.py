from ytops import reports
from ytops.reports import display_width


def test_tsv_and_table_with_korean_width():
    rows = [{"name": "숨비찰나", "n": 12}, {"name": "BACK THEN", "n": None}]
    assert reports.tsv(rows, ["name", "n"]) == "name\tn\n숨비찰나\t12\nBACK THEN\t-"
    lines = reports.table(rows, ["name", "n"]).splitlines()
    assert len({display_width(line) for line in lines}) == 1
    assert display_width("숨비찰나") == 8
    assert lines[3].rstrip().endswith("-")
