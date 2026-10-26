import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import previews as p


class Diff(unittest.TestCase):
    def test_added_changed_removed(self):
        base = {"a": "1", "b": "2", "c": "3"}
        head = {"a": "1", "b": "9", "d": "4"}
        self.assertEqual(p.diff(base, head), (["d"], ["b"], ["c"]))

    def test_nothing_changed(self):
        self.assertEqual(p.diff({"a": "1"}, {"a": "1"}), ([], [], []))


class Manifest(unittest.TestCase):
    def test_hashes_the_pngs_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x.Y.png").write_bytes(b"one")
            (Path(d) / "failed.txt").write_text("ignored")
            m = p.manifest_of(d, "abc")
        self.assertEqual(m["sha"], "abc")
        self.assertEqual(list(m["previews"]), ["x.Y"])


class Names(unittest.TestCase):
    def test_short_name_is_file_and_function(self):
        self.assertEqual(p.short_name("com.app.ui.HomePageContentKt.PreviewEmpty"), "HomePageContent · PreviewEmpty")


def manifest(sha, previews):
    return {"sha": sha, "previews": previews}


class Comment(unittest.TestCase):
    def body(self, base, head, now=None):
        return p.comment_body("o/r", "br-1-1", head, base, now)

    def test_no_baseline(self):
        self.assertIn("not rendered yet", self.body(None, manifest("h" * 40, {})))

    def test_no_change(self):
        m = manifest("a" * 40, {"c.F.P": "1"})
        body = self.body(m, manifest("b" * 40, {"c.F.P": "1"}))
        self.assertIn("No preview changed", body)
        self.assertTrue(body.startswith(p.MARKER))

    def test_shows_before_and_after(self):
        body = self.body(manifest("a" * 40, {"c.F.P": "1", "c.F.Q": "1"}),
                         manifest("b" * 40, {"c.F.P": "2", "c.F.R": "1"}))
        self.assertIn("1 new, 1 modified, 1 removed", body)
        self.assertIn("releases/download/previews-main/c.F.P.png", body)
        self.assertIn("releases/download/br-1-1/c.F.P.png", body)
        # a new one has no before, a removed one no after
        self.assertNotIn("previews-main/c.F.R.png", body)
        self.assertNotIn("br-1-1/c.F.Q.png", body)

    def test_warns_when_main_moved(self):
        m = manifest("a" * 40, {})
        self.assertIn("has moved on", self.body(m, m, now="c" * 40))
        self.assertNotIn("has moved on", self.body(m, m, now="a" * 40))

    def test_long_lists_are_cut(self):
        head = manifest("b" * 40, {f"c.F.P{i:02d}": "1" for i in range(p.MAX_SHOWN + 3)})
        body = self.body(manifest("a" * 40, {}), head)
        self.assertIn("Not shown", body)
        self.assertEqual(body.count("<img"), p.MAX_SHOWN)


if __name__ == "__main__":
    unittest.main()
