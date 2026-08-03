from pathlib import Path


def test_mcp_has_no_mutation_or_sql_tools() -> None:
    source = Path("mcp_server/server.py").read_text(encoding="utf-8")
    prohibited = ["def delete_", "def update_", "def insert_", "def execute_sql", "def query_sql"]
    assert not any(item in source for item in prohibited)
    assert "MAX_RESULTS = 100" in source


def test_mcp_people_query_omits_contact_details() -> None:
    source = Path("mcp_server/server.py").read_text(encoding="utf-8")
    people_projection = source.split("def search_people", 1)[1].split("@mcp.tool()", 1)[0]
    assert "primary_email" not in people_projection
    assert "phone" not in people_projection

