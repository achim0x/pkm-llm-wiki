"""Überschriften, deren Text auf # plus Ziffern endet (Spezifikation 0.13: 4.8, 8, 14, 16 Nr. 21)."""

import pytest

from pkm.errors import PkmError
from pkm.lint import lint
from pkm.maint import Maintenance

from .conftest import write


def findings(svc, path):
    return [(f["check"], f["severity"]) for f in lint(svc)["findings"] if f.get("path") == path]


def test_lint_suffix_like_warning(svc, cfg):
    write(cfg, "documents/a.md", "---\nid: d-20261031-2340-k7q2\nversion: 1\n---\n## Version#2\nx\n")
    f = findings(svc, "documents/a.md")
    assert ("heading_suffix_like", "warning") in f
    assert not any(c in ("heading_suffix_collision", "heading_bad_chars", "duplicate_heading") for c, _ in f)


def test_lint_suffix_collision_error(svc, cfg):
    write(cfg, "documents/a.md", "---\nid: d-20261031-2340-k7q2\nversion: 1\n---\n"
          "## Version\na\n## Version#2\nb\n## Version\nc\n")
    f = findings(svc, "documents/a.md")
    assert ("heading_suffix_collision", "error") in f
    assert ("duplicate_heading", "warning") in f
    assert f.count(("duplicate_heading", "warning")) == 1
    assert ("heading_suffix_like", "warning") not in f


def test_lint_bad_chars_still_reported(svc, cfg):
    write(cfg, "documents/a.md", "---\nid: d-20261031-2340-k7q2\nversion: 1\n---\n## A [x]#2\n")
    f = findings(svc, "documents/a.md")
    assert ("heading_bad_chars", "warning") in f and ("heading_suffix_like", "warning") in f


def test_append_literal_suffix_not_ambiguous(svc):
    d = svc.create_document(title="V", content="## Version\na\n## Version#2\nb\n")
    r = svc.append_to_document(target=d["path"], text="neu", expected_hash=d["new_hash"], section="Version")
    assert svc.read(d["path"])["content"] == "\n## Version\na\n\nneu\n\n## Version#2\nb\n"
    svc.append_to_document(target=d["path"], text="zu b", expected_hash=r["new_hash"], section="Version#2")
    assert svc.read(d["path"])["content"].endswith("## Version#2\nb\n\nzu b\n")


def test_append_duplicate_with_literal(svc):
    d = svc.create_document(title="V2", content="## Version\na\n## Version#2\nb\n## Version\nc\n")
    with pytest.raises(PkmError) as e:
        svc.append_to_document(target=d["path"], text="x", expected_hash=d["new_hash"], section="Version")
    assert e.value.status == "ambiguous" and e.value.data["candidates"] == ["Version", "Version#3"]
    svc.append_to_document(target=d["path"], text="zu c", expected_hash=d["new_hash"], section="Version#3")
    assert svc.read(d["path"])["content"].endswith("## Version\nc\n\nzu c\n")


def test_pending_suffix_shift_is_rename(svc):
    """Kommt eine wörtliche Überschrift hinzu, verschiebt sich das Suffix → renamed."""
    d = svc.create_document(title="V3", content="## Version\na\n## Version\nc\n")
    m = Maintenance(svc)
    m.mark([d["id"]])
    svc.edit_document(target=d["path"], old="a\n## Version\n", new="a\n## Version#2\nb\n## Version\n",
                      expected_hash=d["new_hash"])
    secs = m.pending()["changed"][0]["sections"]
    assert {"key": "Version#3", "change": "renamed", "from": "Version#2"} in secs
    assert {"key": "Version#2", "change": "added"} in secs
