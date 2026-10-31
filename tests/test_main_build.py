import unittest

import _paths  # noqa: F401
import main_build as m


class ReleaseNotes(unittest.TestCase):
    SHA = "a" * 40

    def test_the_commit_is_the_first_line_and_can_be_read_back(self):
        notes = m.release_notes(self.SHA, "2026-10-27 08:00 UTC", "https://github.com/o/r/actions/runs/1")
        self.assertEqual(notes.splitlines()[0], f"commit: {self.SHA}")
        self.assertEqual(m.commit_of(notes), self.SHA)

    def test_no_commit_in_foreign_notes(self):
        self.assertIsNone(m.commit_of("Debug build generated automatically"))
        self.assertIsNone(m.commit_of(None))
        self.assertIsNone(m.commit_of("commit: abc"))


if __name__ == "__main__":
    unittest.main()
