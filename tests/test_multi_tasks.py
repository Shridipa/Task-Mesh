from taskmesh.json_validation import validate_json
from taskmesh.csv_analysis import analyze_csv

def test_json_valid_format_and_counts():
    r=validate_json('{"a":[1,{"b":true}]}')
    assert r["valid"] and r["objects"]==2 and r["arrays"]==1 and r["keys"]==2

def test_json_invalid_reports_location():
    r=validate_json('{"a":')
    assert not r["valid"] and r["line"]==1 and r["column"]>0

def test_csv_statistics_and_duplicates():
    r=analyze_csv('name,value\na,1\nb,3\nb,3\n')
    assert r["rows"]==3 and r["numeric_statistics"]["value"]["mean"]==2
    assert r["duplicate_rows"]==1

def test_csv_missing_values():
    r=analyze_csv('a,b\n1,\n2,3\n')
    assert r["missing_values"]["b"]==1
