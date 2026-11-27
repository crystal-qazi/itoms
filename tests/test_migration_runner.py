"""SQL migration parser regression tests."""
from itoms.db.migrations.runner import split_sql_statements


def test_splitter_ignores_semicolons_in_line_comments_and_literals():
    sql = """-- Header comment; still a comment
CREATE TABLE sample (value VARCHAR(40));
-- A comment with a semicolon; and another
INSERT INTO sample(value) VALUES ('alpha;beta');
"""
    assert split_sql_statements(sql) == [
        "CREATE TABLE sample (value VARCHAR(40))",
        "INSERT INTO sample(value) VALUES ('alpha;beta')",
    ]


def test_splitter_ignores_semicolons_in_block_comments_and_backticks():
    sql = """/* migration note; with delimiter */ 
CREATE TABLE `sample;table` (value VARCHAR(40)); # comment;
SELECT 'it''s; valid', "double;quoted";
"""
    assert split_sql_statements(sql) == [
        "CREATE TABLE `sample;table` (value VARCHAR(40))",
        """SELECT 'it''s; valid', "double;quoted" """.strip(),
    ]


def test_splitter_handles_escaped_quotes_and_trailing_statement():
    sql = r"""INSERT INTO sample(value) VALUES ('a\\';b'); SELECT 1"""
    assert split_sql_statements(sql) == [
        r"""INSERT INTO sample(value) VALUES ('a\\';b')""",
        "SELECT 1",
    ]
