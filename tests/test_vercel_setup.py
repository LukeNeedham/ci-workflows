"""Tests for vercel_setup.py, and its step in new_app.py. Run: python3 -m unittest discover -s tests"""

import unittest

import _paths  # noqa: F401
import new_app as n
import vercel_setup as v


class FakeVercel:
    """A `call` that answers from a table of (method, path) -> (status, json) and records what it was asked. A list is taken one at a time."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        answer = self.answers.get((method, path), (404, {"error": {"code": "not_found", "message": "Not found"}}))
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        return answer


def project(**fields):
    return {"id": "prj_1", "name": "my-site", "link": {"type": "github", "org": "LukeNeedham", "repo": "MySite"}, **fields}


GET = ("GET", "/v9/projects/my-site")
CREATE = ("POST", "/v11/projects")
PATCH = ("PATCH", "/v9/projects/prj_1")
GET_ID = ("GET", "/v9/projects/prj_1")
PROTECTED = {"ssoProtection": {"deploymentType": "all_except_custom_domains"}}


class Names(unittest.TestCase):
    def test_the_project_name_is_what_vercel_accepts(self):
        self.assertEqual("my-site", v.project_name("My_Site".replace("_", "-")))
        self.assertEqual("my_site", v.project_name("My_Site"))
        self.assertEqual("lt-companion", v.project_name("LT-Companion"))
        self.assertEqual("a--b", v.project_name("a-----b"), "never three dashes")
        self.assertEqual(100, len(v.project_name("x" * 150)))

    def test_a_name_that_is_all_punctuation_is_refused(self):
        with self.assertRaises(ValueError):
            v.project_name("---")


class EnsureProject(unittest.TestCase):
    def test_a_missing_project_is_created_connected_to_the_repo_as_next_js(self):
        call = FakeVercel({GET: (404, {}), CREATE: (200, project())})

        found, created = v.ensure_project(call, "my-site", "LukeNeedham/MySite")

        self.assertTrue(created)
        self.assertEqual({"name": "my-site", "framework": "nextjs", "gitRepository": {"type": "github", "repo": "LukeNeedham/MySite"}},
                         call.calls[-1][2])

    def test_a_project_that_is_there_and_connected_to_the_repo_is_not_touched(self):
        call = FakeVercel({GET: (200, project())})
        found, created = v.ensure_project(call, "my-site", "lukeneedham/mysite")
        self.assertFalse(created)
        self.assertEqual([("GET", "/v9/projects/my-site", None)], call.calls)

    def test_a_project_of_the_name_that_belongs_to_another_repo_is_an_error(self):
        call = FakeVercel({GET: (200, project(link={"type": "github", "org": "Someone", "repo": "Else"}))})
        with self.assertRaisesRegex(v.VercelError, "connected to Someone/Else, not LukeNeedham/MySite"):
            v.ensure_project(call, "my-site", "LukeNeedham/MySite")

    def test_a_project_connected_to_no_repo_is_an_error_and_not_taken_over(self):
        call = FakeVercel({GET: (200, project(link=None))})
        with self.assertRaisesRegex(v.VercelError, "connected to no repo"):
            v.ensure_project(call, "my-site", "LukeNeedham/MySite")
        self.assertEqual(1, len(call.calls))

    def test_a_refused_connection_says_to_install_the_github_app(self):
        error = {"error": {"code": "invalid_git_repository", "message": "Could not find the GitHub repository"}}
        call = FakeVercel({GET: (404, {}), CREATE: (400, error)})
        with self.assertRaisesRegex(v.VercelError, "All repositories") as e:
            v.ensure_project(call, "my-site", "LukeNeedham/MySite")
        self.assertEqual(400, e.exception.status)

    def test_the_message_names_the_page_where_the_access_is_given(self):
        error = {"error": {"code": "repo_not_found", "message": 'The repository "MySite" couldn\'t be found.'}}
        call = FakeVercel({GET: (404, {}), CREATE: (400, error)})
        with self.assertRaises(v.VercelError) as e:
            v.ensure_project(call, "my-site", "LukeNeedham/MySite")
        self.assertIn(v.GITHUB_APP_SETTINGS, str(e.exception))
        self.assertIn("repo_not_found", str(e.exception))
        self.assertIn("reconnect GitHub", str(e.exception), "an expired connection of the Vercel account gives the same error")

    def test_a_bad_token_says_so(self):
        call = FakeVercel({GET: (403, {"error": {"code": "forbidden", "message": "Not authorized"}})})
        with self.assertRaisesRegex(v.VercelError, "VERCEL_TOKEN"):
            v.ensure_project(call, "my-site", "LukeNeedham/MySite")


LIST = ("GET", "/v9/projects?limit=100")


class FindLinkedProject(unittest.TestCase):
    def test_a_project_connected_to_the_repo_is_found_whatever_it_is_called(self):
        other = project(id="prj_9", name="other", link={"org": "LukeNeedham", "repo": "Else"})
        mine = project(name="personal-website", link={"org": "LukeNeedham", "repo": "PersonalWebsite"})
        call = FakeVercel({LIST: (200, {"projects": [other, mine]})})
        self.assertEqual("personal-website", v.find_linked_project(call, "lukeneedham/personalwebsite")["name"])

    def test_no_project_connected_to_the_repo_is_none(self):
        call = FakeVercel({LIST: (200, {"projects": [project(link={"org": "LukeNeedham", "repo": "Else"}), project(link=None)]})})
        self.assertIsNone(v.find_linked_project(call, "LukeNeedham/MySite"))

    def test_the_next_page_is_read_when_there_is_one(self):
        second = ("GET", "/v9/projects?limit=100&until=123")
        call = FakeVercel({
            LIST: (200, {"projects": [], "pagination": {"next": 123}}),
            second: (200, {"projects": [project()], "pagination": {"next": None}}),
        })
        self.assertEqual("my-site", v.find_linked_project(call, "LukeNeedham/MySite")["name"])

    def test_a_list_that_fails_is_an_error_and_not_taken_for_no_project(self):
        call = FakeVercel({LIST: (403, {"error": {"code": "forbidden", "message": "Not authorized"}})})
        with self.assertRaisesRegex(v.VercelError, "Listing the Vercel projects"):
            v.find_linked_project(call, "LukeNeedham/MySite")

    def test_the_site_is_set_up_in_its_existing_project_and_no_second_one_is_made(self):
        existing = project(name="personal-website", link={"org": "LukeNeedham", "repo": "PersonalWebsite"}, ssoProtection=None)
        call = FakeVercel({LIST: (200, {"projects": [existing]}), ("GET", "/v9/projects/personal-website"): (200, existing)})

        lines = v.set_up(call, "LukeNeedham/PersonalWebsite")

        self.assertEqual("vercel project personal-website already connected to LukeNeedham/PersonalWebsite", lines[0])
        self.assertFalse([c for c in call.calls if c[0] == "POST"])


class OpenPreviews(unittest.TestCase):
    def test_protection_is_turned_off_and_read_back(self):
        call = FakeVercel({PATCH: (200, project()), GET_ID: (200, project(ssoProtection=None))})

        changed = v.open_previews(call, project(**PROTECTED))

        self.assertTrue(changed)
        self.assertEqual(("PATCH", "/v9/projects/prj_1", {"ssoProtection": None}), call.calls[0])

    def test_a_project_that_is_open_already_is_left_alone(self):
        call = FakeVercel({})
        self.assertFalse(v.open_previews(call, project(ssoProtection=None)))
        self.assertFalse(v.open_previews(call, project()))
        self.assertEqual([], call.calls)

    def test_a_setting_that_did_not_take_is_an_error_not_a_success(self):
        call = FakeVercel({PATCH: (200, project()), GET_ID: (200, project(**PROTECTED))})
        with self.assertRaisesRegex(v.VercelError, "still has Deployment Protection on"):
            v.open_previews(call, project(**PROTECTED))

    def test_a_refusal_of_the_plan_is_an_error(self):
        call = FakeVercel({PATCH: (402, {"error": {"code": "payment_required", "message": "Upgrade your plan"}})})
        with self.assertRaisesRegex(v.VercelError, "Upgrade your plan"):
            v.open_previews(call, project(**PROTECTED))


OFF = {"gitProviderOptions": {"createDeployments": "disabled", "disableRepositoryDispatchEvents": True}}


class GithubDeployments(unittest.TestCase):
    def test_a_project_made_through_the_api_has_them_off_and_the_default_has_them_on(self):
        self.assertFalse(v.github_deployments_are_on(project(**OFF)))
        self.assertTrue(v.github_deployments_are_on(project()))
        self.assertTrue(v.github_deployments_are_on(project(gitProviderOptions=None)))
        self.assertTrue(v.github_deployments_are_on(project(gitProviderOptions={"createDeployments": "enabled"})))

    def test_they_are_turned_on_keeping_the_other_options_and_read_back(self):
        on = project(gitProviderOptions={"createDeployments": "enabled", "disableRepositoryDispatchEvents": True})
        call = FakeVercel({PATCH: (200, on), GET_ID: (200, on)})

        changed = v.enable_github_deployments(call, project(**OFF))

        self.assertTrue(changed)
        self.assertEqual(("PATCH", "/v9/projects/prj_1", {"gitProviderOptions": {"createDeployments": "enabled", "disableRepositoryDispatchEvents": True}}),
                         call.calls[0])

    def test_a_project_that_has_them_on_is_left_alone(self):
        call = FakeVercel({})
        self.assertFalse(v.enable_github_deployments(call, project()))
        self.assertEqual([], call.calls)

    def test_a_setting_that_did_not_take_is_an_error(self):
        call = FakeVercel({PATCH: (200, project(**OFF)), GET_ID: (200, project(**OFF))})
        with self.assertRaisesRegex(v.VercelError, "still has GitHub deployments off"):
            v.enable_github_deployments(call, project(**OFF))

    def test_a_new_site_has_them_turned_on_by_the_setup(self):
        on = project(gitProviderOptions={"createDeployments": "enabled"})
        call = FakeVercel({GET: (404, {}), CREATE: (200, project(**OFF)), GET_ID: (200, on), PATCH: (200, on)})
        # the project is made with them off, and public previews already: only the GitHub deployments change
        call.answers[CREATE] = (200, project(**OFF, ssoProtection=None))

        lines = v.set_up(call, "LukeNeedham/MySite", "my-site")

        self.assertEqual("vercel github deployments: turned on", lines[-1])


class SetUp(unittest.TestCase):
    def test_a_new_site_gets_a_project_and_open_previews(self):
        call = FakeVercel({GET: (404, {}), CREATE: (200, project(**PROTECTED)), PATCH: (200, project()), GET_ID: (200, project())})
        lines = v.set_up(call, "LukeNeedham/MySite", "my-site")  # a name is given: no search
        self.assertEqual(["vercel project my-site created and connected to LukeNeedham/MySite",
                          "vercel previews: Deployment Protection turned off",
                          "vercel github deployments: were on already"], lines)

    def test_running_it_again_changes_nothing(self):
        call = FakeVercel({GET: (200, project(ssoProtection=None))})
        lines = v.set_up(call, "LukeNeedham/MySite", "my-site")
        self.assertEqual(["vercel project my-site already connected to LukeNeedham/MySite",
                          "vercel previews: Deployment Protection was off already",
                          "vercel github deployments: were on already"], lines)
        self.assertEqual(["GET"], [c[0] for c in call.calls])

    def test_the_project_is_named_after_the_repo_by_default(self):
        call = FakeVercel({LIST: (200, {"projects": []}),
                           ("GET", "/v9/projects/personalwebsite"): (200, project(name="personalwebsite", link={"org": "LukeNeedham", "repo": "PersonalWebsite"}))})
        self.assertIn("vercel project personalwebsite already", v.set_up(call, "LukeNeedham/PersonalWebsite")[0])


class NewAppStep(unittest.TestCase):
    def test_without_a_token_the_step_is_skipped_and_says_what_is_left(self):
        lines = n.set_up_vercel("LukeNeedham/MySite", "MySite", None, None, lambda *a: self.fail("called"))
        self.assertEqual(1, len(lines))
        self.assertIn("no VERCEL_TOKEN", lines[0])
        self.assertIn("Deployment Protection", lines[0])

    def test_with_a_token_the_site_is_set_up_with_the_team(self):
        made = []

        def make_call(token, team):
            made.append((token, team))
            return FakeVercel({LIST: (200, {"projects": []}), ("GET", "/v9/projects/mysite"): (200, project(name="mysite", link={"org": "LukeNeedham", "repo": "MySite"}, ssoProtection=None))})

        lines = n.set_up_vercel("LukeNeedham/MySite", "MySite", "tok", "team_1", make_call)

        self.assertEqual([("tok", "team_1")], made)
        self.assertTrue(lines[0].startswith("vercel project mysite"))

    def test_a_failure_says_the_repo_is_made_and_how_to_carry_on(self):
        error = {"error": {"code": "repo_not_found", "message": "The repository could not be found"}}

        def make_call(token, team):
            return FakeVercel({LIST: (200, {"projects": []}), ("GET", "/v9/projects/mysite"): (404, {}), CREATE: (400, error)})

        with self.assertRaises(v.VercelError) as e:
            n.set_up_vercel("LukeNeedham/MySite", "MySite", "tok", None, make_call)

        text = str(e.exception)
        self.assertIn("repo and its first commit are made", text)
        self.assertIn("run New App again for MySite with resume on", text)
        self.assertIn("All repositories", text)
        self.assertEqual(400, e.exception.status)

    def test_the_next_steps_leave_out_vercel_when_it_is_done(self):
        by_hand = n.next_steps("MySite", "next-js")
        done = n.next_steps("MySite", "next-js", vercel_done=True)
        self.assertIn("Connect the repo to a project on Vercel", by_hand)
        self.assertNotIn("Vercel", done)
        self.assertIn("Claude GitHub App", done)


if __name__ == "__main__":
    unittest.main()
