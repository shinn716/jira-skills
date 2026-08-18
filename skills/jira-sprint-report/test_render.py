#!/usr/bin/env python3
"""Smoke test: render sample-sprint.json and check the numbers came out right.

    python skills/jira-sprint-report/test_render.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    out = os.path.join(tempfile.mkdtemp(), "out.html")
    r = subprocess.run(
        [sys.executable, os.path.join(HERE, "render.py"),
         os.path.join(HERE, "sample-sprint.json"), out],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    # 3 of jane's issues (PROJ-101/102/103), 2 done; sprint has 5 after dedupe of PROJ-105
    assert "jane.doe: 3 issues, 2 done, 1 unfinished (sprint: 5 issues, 3 done)" in r.stdout, r.stdout

    html = open(out, encoding="utf-8").read()
    assert html.startswith("<!doctype html>")
    assert html.count("PROJ-105") == 0, "team-only issue leaked into my table"
    assert "<code>app.config</code>" in html, "wiki {{...}} not rendered as code"
    assert "67%" in html, "completion tile wrong"
    assert "Sam Lee" in html, "team comparison missing"
    assert "<code>total</code>" in html, "Markdown `...` not rendered as code"
    assert 'id="f-v"' in html, "fix version filter missing"
    assert '<option value="1.4.0">1.4.0 (2)</option>' in html, "fix version counts wrong"
    assert 'data-v="|1.4.0|1.10.0|"' in html, "multi-version row not pipe-wrapped"
    # 1.4.0 before 1.10.0: digit runs sort as numbers, not as text
    assert html.index('value="1.4.0"') < html.index('value="1.10.0"'), "versions sorted as text"
    assert '<option value="">All' in html and html.count('<option value="">') == 3, \
        "a nameless fix version leaked in as an empty option"

    print("OK", out)


if __name__ == "__main__":
    main()
