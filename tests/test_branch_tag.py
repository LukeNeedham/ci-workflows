import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "actions" / "branch-tag"))
import branch_tag  # noqa: E402


class BranchTagTest(unittest.TestCase):
    def test_clean_branch_replaces_specials_and_lowercases(self):
        self.assertEqual(branch_tag.clean_branch("Feature/Add Thing"), "feature-add-thing")

    def test_release_tag(self):
        self.assertEqual(branch_tag.release_tag("ccr-1/x", 208, 1), "ccr-1-x-208-1")

    def test_matches_own_tags_only(self):
        self.assertTrue(branch_tag.matches("foo-12-1", "foo"))
        # another branch whose name merely starts with this one
        self.assertFalse(branch_tag.matches("foo-bar-12-1", "foo"))
        self.assertFalse(branch_tag.matches("foo-12", "foo"))
        self.assertFalse(branch_tag.matches("foo-12-1-extra", "foo"))

    def test_matches_roundtrips_release_tag(self):
        for branch in ["main", "a/b", "Weird Name!", "x.y_z"]:
            self.assertTrue(branch_tag.matches(branch_tag.release_tag(branch, 5, 2), branch))

    def test_select_tags_ignores_full_releases(self):
        releases = [
            {"tagName": "foo-1-1", "isPrerelease": True},
            {"tagName": "foo-2-1", "isPrerelease": False},
            {"tagName": "other-3-1", "isPrerelease": True},
        ]
        self.assertEqual(branch_tag.select_tags(releases, "foo"), ["foo-1-1"])


if __name__ == "__main__":
    unittest.main()
