from taskmesh.tasks import execute_job

def test_dispatch_json_job():
    result=execute_job("json.validate",{"json_text":"{\\"x\\":1}"})
    assert result["valid"]

def test_dispatch_csv_job():
    result=execute_job("csv.analyze",{"csv_text":"x\\n1\\n2\\n"})
    assert result["rows"]==2
