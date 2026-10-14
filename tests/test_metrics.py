import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gitlab_languages import gitlab_languages


class FakeProject:
    def __init__(
        self,
        project_id,
        name,
        languages,
        statistics=None,
        last_activity_at="2024-01-01T00:00:00.000Z",
    ):
        self.id = project_id
        self.name = name
        self.attributes = {"last_activity_at": last_activity_at}
        if statistics is not None:
            self.attributes["statistics"] = statistics
        self._languages = languages

    def languages(self):
        return self._languages


class FakeProjectsApi:
    def __init__(self):
        self.calls = []
        self.by_id = {}

    def get(self, project_id, statistics=False, simple=False):
        self.calls.append(
            {"id": project_id, "statistics": statistics, "simple": simple}
        )
        return self.by_id[project_id]


class FakeGitlab:
    def __init__(self):
        self.projects = FakeProjectsApi()


class FakeHelper:
    def __init__(self, gl):
        self.gl = gl


class MetricsCalculationTest(unittest.TestCase):
    def test_equal_weight_matches_historical_average(self):
        collector = gitlab_languages.MetricsCollector()
        collector.record_project([("Python", 60), ("JavaScript", 40)], 1)
        collector.record_project([("Python", 10), ("Go", 90)], 1)

        percentages = collector.percentages(projects_scanned=2)

        self.assertAlmostEqual(percentages["Python"], 35)
        self.assertAlmostEqual(percentages["JavaScript"], 20)
        self.assertAlmostEqual(percentages["Go"], 45)
        self.assertAlmostEqual(sum(percentages.values()), 100)

    def test_repository_size_gives_large_projects_more_weight(self):
        collector = gitlab_languages.MetricsCollector()
        # 10 bytes of Python must not count the same as 10_000 bytes of Java.
        collector.record_project([("Python", 100)], 10)
        collector.record_project([("Java", 100)], 10_000)

        percentages = collector.percentages()

        self.assertAlmostEqual(percentages["Python"], 10 / 10010 * 100)
        self.assertAlmostEqual(percentages["Java"], 10000 / 10010 * 100)
        self.assertLess(percentages["Python"], 1)
        self.assertGreater(percentages["Java"], 99)

    def test_absolute_line_counts_are_used_when_present(self):
        collector = gitlab_languages.MetricsCollector()
        collector.record_project(
            [("Python", {"percentage": 100, "sloc": 10})], project_weight=999
        )
        collector.record_project(
            [("Java", {"percentage": 100, "lines": 10_000})], project_weight=1
        )

        percentages = collector.percentages()

        self.assertAlmostEqual(percentages["Python"], 10 / 10010 * 100)
        self.assertAlmostEqual(percentages["Java"], 10000 / 10010 * 100)

    def test_absolute_bytes_ignore_project_weight(self):
        contributions, weight_used = gitlab_languages.project_language_contributions(
            [("Python", {"bytes": 80, "share": 80}), ("Go", {"bytes": 20})],
            project_weight=5,
        )

        self.assertEqual(weight_used, 100)
        self.assertEqual(contributions, [("Python", 100.0, 80), ("Go", 100.0, 20)])

    def test_missing_percentage_is_skipped(self):
        contributions, weight_used = gitlab_languages.project_language_contributions(
            [("Python", None), ("Go", 100)],
            project_weight=4,
        )

        self.assertEqual(contributions, [("Go", 100, 4.0)])
        self.assertEqual(weight_used, 4.0)


class LanguageScannerWeightTest(unittest.TestCase):
    def setUp(self):
        self._language_cache = gitlab_languages.language_cache
        self._gitlab_url = gitlab_languages.gitlab_url
        gitlab_languages.language_cache = None
        gitlab_languages.gitlab_url = "https://gitlab.example"

    def tearDown(self):
        gitlab_languages.language_cache = self._language_cache
        gitlab_languages.gitlab_url = self._gitlab_url

    def _scanner(self, weight=gitlab_languages.WEIGHT_REPOSITORY_SIZE):
        gl = FakeGitlab()
        return gitlab_languages.LanguageScanner(FakeHelper(gl), weight=weight), gl

    def test_fetches_statistics_and_weights_by_repository_size(self):
        scanner, gl = self._scanner()
        gl.projects.by_id[1] = FakeProject(
            1, "tiny", {"Python": 100}, statistics={"repository_size": 10}
        )
        gl.projects.by_id[2] = FakeProject(
            2, "huge", {"Java": 100}, statistics={"repository_size": 10_000}
        )

        scanner.scan(FakeProject(1, "tiny", {"Python": 100}))
        scanner.scan(FakeProject(2, "huge", {"Java": 100}))

        self.assertEqual(
            [call["statistics"] for call in gl.projects.calls], [True, True]
        )
        percentages = scanner.metrics_collector.percentages()
        self.assertAlmostEqual(percentages["Python"], 10 / 10010 * 100)
        self.assertAlmostEqual(percentages["Java"], 10000 / 10010 * 100)
        self.assertEqual(scanner.projects_scanned, 2)
        self.assertEqual(scanner.repository_size_bytes, 10010)
        self.assertEqual(scanner.projects_missing_size, 0)
        self.assertEqual(
            gitlab_languages.language_cache["https://gitlab.example"]["1"][2], 10
        )

    def test_uses_statistics_already_present_on_the_project(self):
        scanner, gl = self._scanner()
        scanner.scan(
            FakeProject(
                1,
                "already-loaded",
                {"Python": 80, "Go": 20},
                statistics={"repository_size": 500},
            )
        )

        self.assertEqual(gl.projects.calls, [])
        percentages = scanner.metrics_collector.percentages()
        self.assertAlmostEqual(percentages["Python"], 80)
        self.assertAlmostEqual(percentages["Go"], 20)
        self.assertEqual(scanner.repository_size_bytes, 500)

    def test_stale_cache_refetches_repository_size(self):
        gitlab_languages.language_cache = {
            "https://gitlab.example": {
                "7": ["2020-01-01T00:00:00.000Z", [["Python", 100]], 1]
            }
        }
        scanner, gl = self._scanner()
        gl.projects.by_id[7] = FakeProject(
            7,
            "moved",
            {"Java": 100},
            statistics={"repository_size": 80},
            last_activity_at="2024-06-01T00:00:00.000Z",
        )
        scanner.scan(
            FakeProject(
                7,
                "moved",
                {"Java": 100},
                last_activity_at="2024-06-01T00:00:00.000Z",
            )
        )

        self.assertEqual(gl.projects.calls[0]["statistics"], True)
        self.assertEqual(scanner.repository_size_bytes, 80)
        self.assertAlmostEqual(scanner.metrics_collector.percentages()["Java"], 100)
        self.assertEqual(
            gitlab_languages.language_cache["https://gitlab.example"]["7"][2], 80
        )

    def test_unreadable_cache_timestamp_does_not_abort_scan(self):
        gitlab_languages.language_cache = {
            "https://gitlab.example": {"7": ["not-a-date", [["Python", 1]], 1]}
        }
        scanner, gl = self._scanner()
        gl.projects.by_id[7] = FakeProject(
            7, "bad-cache", {"Python": 100}, statistics={"repository_size": 5}
        )
        scanner.scan(FakeProject(7, "bad-cache", {"Python": 100}))

        self.assertEqual(scanner.projects_scanned, 1)
        self.assertEqual(scanner.repository_size_bytes, 5)
        self.assertEqual(gl.projects.calls[0]["statistics"], True)

    def test_cached_size_skips_statistics_request(self):
        gitlab_languages.language_cache = {
            "https://gitlab.example": {
                "7": ["2024-01-01T00:00:00.000Z", [["Python", 100]], 42]
            }
        }
        scanner, gl = self._scanner()
        scanner.scan(FakeProject(7, "cached", {"Python": 100}))

        self.assertEqual(gl.projects.calls, [])
        self.assertEqual(scanner.repository_size_bytes, 42)
        self.assertAlmostEqual(scanner.metrics_collector.percentages()["Python"], 100)

    def test_missing_size_falls_back_to_one_byte(self):
        scanner, gl = self._scanner()
        gl.projects.by_id[1] = FakeProject(1, "unknown", {"Python": 100})
        gl.projects.by_id[2] = FakeProject(
            2, "known", {"Java": 100}, statistics={"repository_size": 100}
        )

        scanner.scan(FakeProject(1, "unknown", {"Python": 100}))
        scanner.scan(FakeProject(2, "known", {"Java": 100}))

        percentages = scanner.metrics_collector.percentages()
        self.assertAlmostEqual(percentages["Python"], 1 / 101 * 100)
        self.assertAlmostEqual(percentages["Java"], 100 / 101 * 100)
        self.assertEqual(scanner.projects_missing_size, 1)
        self.assertEqual(scanner.repository_size_bytes, 100)

    def test_equal_weight_does_not_request_statistics(self):
        scanner, gl = self._scanner(weight=gitlab_languages.WEIGHT_EQUAL)
        scanner.scan(
            FakeProject(1, "tiny", {"Python": 100}, statistics={"repository_size": 10})
        )
        scanner.scan(
            FakeProject(
                2, "huge", {"Java": 100}, statistics={"repository_size": 10_000}
            )
        )

        self.assertEqual(gl.projects.calls, [])
        percentages = scanner.metrics_collector.percentages()
        self.assertAlmostEqual(percentages["Python"], 50)
        self.assertAlmostEqual(percentages["Java"], 50)
        self.assertEqual(scanner.repository_size_bytes, 0)

    def test_zero_size_does_not_drop_the_project(self):
        scanner, _gl = self._scanner()
        scanner.scan(
            FakeProject(1, "empty", {"Python": 100}, statistics={"repository_size": 0})
        )
        scanner.scan(
            FakeProject(2, "real", {"Java": 100}, statistics={"repository_size": 100})
        )

        percentages = scanner.metrics_collector.percentages()
        self.assertAlmostEqual(percentages["Python"], 1 / 101 * 100)
        self.assertEqual(scanner.projects_missing_size, 0)
        self.assertEqual(scanner.projects_scanned, 2)

    def test_project_without_languages_is_not_weighted(self):
        scanner, gl = self._scanner()
        scanner.scan(FakeProject(1, "docs", {}))

        self.assertEqual(scanner.projects_no_language, 1)
        self.assertEqual(scanner.projects_scanned, 0)
        self.assertEqual(gl.projects.calls, [])

    def test_ignored_project_is_skipped(self):
        gl = FakeGitlab()
        scanner = gitlab_languages.LanguageScanner(FakeHelper(gl), ignored_projects=[3])
        scanner.scan(FakeProject(3, "skip", {"Python": 100}))

        self.assertEqual(scanner.projects_skipped, 1)
        self.assertEqual(scanner.projects_scanned, 0)
        self.assertEqual(gl.projects.calls, [])

    def test_write_includes_size_gauges(self):
        scanner, _gl = self._scanner()
        scanner.scan(
            FakeProject(1, "app", {"Python": 100}, statistics={"repository_size": 250})
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.txt"
            scanner.write_metrics(path)
            text = path.read_text()

        self.assertIn('languages_percent{language="Python"} 100.0', text)
        self.assertIn("repository_size_bytes_total 250.0", text)
        self.assertIn("projects_missing_size_total 0.0", text)
        self.assertIn("projects_scanned_total 1.0", text)

    def test_invalid_weight_is_rejected(self):
        with self.assertRaises(ValueError):
            gitlab_languages.LanguageScanner(FakeHelper(FakeGitlab()), weight="commits")


class HelpTextTest(unittest.TestCase):
    def test_weight_flag_is_documented(self):
        result = subprocess.run(
            [sys.executable, "-m", "gitlab_languages", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("--weight", result.stdout)
        self.assertIn("repository_size", result.stdout)
        self.assertIn("equal", result.stdout)


if __name__ == "__main__":
    unittest.main()
