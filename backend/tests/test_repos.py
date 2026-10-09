# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
from app.repos import list_repos


def test_list_repos_finds_modules_two_levels_deep(tmp_path):
    (tmp_path / "stats").mkdir()
    (tmp_path / "stats" / "go.mod").write_text("module github.com/montanaflynn/stats\n\ngo 1.17\n")
    (tmp_path / "stats" / "mean.go").write_text("package stats\n")
    (tmp_path / "stats" / "mean_test.go").write_text("package stats\n")
    (tmp_path / "org" / "svc").mkdir(parents=True)
    (tmp_path / "org" / "svc" / "go.mod").write_text("module example.com/svc\n")
    (tmp_path / "notgo").mkdir()
    repos = list_repos(tmp_path)
    assert [(r.path, r.module, r.go_files, r.test_files) for r in repos] == [
        ("org/svc", "example.com/svc", 0, 0),
        ("stats", "github.com/montanaflynn/stats", 1, 1),
    ]


def test_list_repos_missing_dir_is_empty(tmp_path):
    assert list_repos(tmp_path / "nope") == []
