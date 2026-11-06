"""Lints the Switch template with Switch's own linter when switch_core is importable."""
import os
import pytest

T = os.path.join(os.path.dirname(__file__), "..", "switch", "twokeys.template.yaml")


def test_template_has_required_shape():
    yaml = pytest.importorskip("yaml")
    d = yaml.safe_load(open(T))
    names = [a["name"] for a in d["agents"]]
    assert names == ["{team}-twokeys-scope", "{team}-twokeys-hands"]
    assert set(d["room"]["agents"]) == set(names)
    assert {r["name"] for r in d["room"]["roles"]} == {"scope", "hands"}
    assert all(r["exclusive"] for r in d["room"]["roles"])
    hands = d["agents"][1]["instructions"]
    assert "list_participants" in hands and "read_context" in hands and "NOT RUN" in hands


def test_switch_linter_accepts_template():
    lint = pytest.importorskip("switch_core.template_lint")
    r = lint.lint_template(open(T).read())
    assert r.ok and not r.blocked, [f.message for f in r.errors]
