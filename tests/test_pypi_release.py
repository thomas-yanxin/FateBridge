"""Publishing gates must skip existing versions and fail closed on API errors."""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest
import yaml

from scripts import check_pypi_release


@pytest.fixture
def release_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RELEASE_TAG", raising=False)
    source = tmp_path / "src/fatebridge/__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text('__version__ = "0.2.0"\nraise RuntimeError("do not import")\n')
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    return source, output


@pytest.mark.parametrize("files,expected", [([], "true"), ([{}], "false")])
def test_pypi_files_control_build_and_publish(
    release_workspace, monkeypatch, files, expected
):
    def request(url, timeout):
        assert url == "https://pypi.org/pypi/fatebridge/0.2.0/json"
        assert timeout == 30
        return io.BytesIO(json.dumps({"urls": files}).encode())

    monkeypatch.setattr(check_pypi_release, "urlopen", request)
    assert check_pypi_release.main() == 0
    assert release_workspace[1].read_text() == f"should_publish={expected}\n"


@pytest.mark.parametrize("status", [404, 403, 429, 500, 503])
def test_only_pypi_404_means_a_new_version(release_workspace, monkeypatch, status):
    def request(*args, **kwargs):
        raise HTTPError("https://pypi.org", status, "fixture", {}, None)

    monkeypatch.setattr(check_pypi_release, "urlopen", request)
    if status == 404:
        assert check_pypi_release.main() == 0
        assert release_workspace[1].read_text() == "should_publish=true\n"
    else:
        with pytest.raises(HTTPError):
            check_pypi_release.main()
        assert not release_workspace[1].exists()


@pytest.mark.parametrize("error", [URLError("offline"), TimeoutError("timeout")])
def test_network_errors_never_authorize_publishing(
    release_workspace, monkeypatch, error
):
    def request(*args, **kwargs):
        raise error

    monkeypatch.setattr(check_pypi_release, "urlopen", request)
    with pytest.raises(type(error)):
        check_pypi_release.main()
    assert not release_workspace[1].exists()


@pytest.mark.parametrize("payload", [b"unavailable", b"{}", b'{"urls": null}'])
def test_invalid_pypi_response_never_authorizes_publishing(
    release_workspace, monkeypatch, payload
):
    monkeypatch.setattr(
        check_pypi_release, "urlopen", lambda *a, **kw: io.BytesIO(payload)
    )
    with pytest.raises((ValueError, KeyError)):
        check_pypi_release.main()
    assert not release_workspace[1].exists()


@pytest.mark.parametrize("tag", ["v0.2.0", "v0.1.0", "0.2.0"])
def test_release_tag_is_checked_before_pypi(release_workspace, monkeypatch, tag):
    monkeypatch.setenv("RELEASE_TAG", tag)
    calls = []
    monkeypatch.setattr(
        check_pypi_release, "already_published", lambda version: calls.append(version)
    )
    if tag == "v0.2.0":
        assert check_pypi_release.main() == 0
        assert calls == ["0.2.0"]
    else:
        with pytest.raises(ValueError, match="does not match"):
            check_pypi_release.main()
        assert calls == []
        assert not release_workspace[1].exists()


@pytest.mark.parametrize("source", ["", "__version__ = 2", '__version__ = ""'])
def test_missing_or_invalid_static_version_is_rejected(tmp_path, source):
    path = tmp_path / "version.py"
    path.write_text(source)
    with pytest.raises(ValueError):
        check_pypi_release.package_version(path)


WORKFLOW = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / ".github/workflows/publish.yml").read_text()
)


@pytest.mark.parametrize(
    "event,conclusion,trigger,branch,same_repo,allowed",
    [
        ("workflow_run", "success", "push", "master", True, True),
        ("workflow_run", "failure", "push", "master", True, False),
        ("workflow_run", "cancelled", "push", "master", True, False),
        ("workflow_run", "skipped", "push", "master", True, False),
        ("workflow_run", "success", "pull_request", "master", True, False),
        ("workflow_run", "success", "push", "feature", True, False),
        ("workflow_run", "success", "push", "master", False, False),
        ("release", "", "", "", True, True),
    ],
)
def test_workflow_entry_gate(event, conclusion, trigger, branch, same_repo, allowed):
    github = SimpleNamespace(
        event_name=event,
        repository="owner/FateBridge",
        event=SimpleNamespace(
            workflow_run=SimpleNamespace(
                conclusion=conclusion,
                event=trigger,
                head_branch=branch,
                head_repository=SimpleNamespace(
                    full_name="owner/FateBridge" if same_repo else "fork/FateBridge"
                ),
            )
        ),
    )
    # Exercise the workflow's actual expression against representative events.
    expression = (
        WORKFLOW["jobs"]["check"]["if"].replace("&&", "and").replace("||", "or")
    )
    assert eval(expression, {"__builtins__": {}}, {"github": github}) is allowed


def test_both_jobs_checkout_the_tested_commit_and_existing_versions_skip_build():
    jobs = WORKFLOW["jobs"]
    for name in ("check", "build"):
        checkout = jobs[name]["steps"][0]
        assert checkout["with"]["ref"] == (
            "${{ github.event.workflow_run.head_sha || github.sha }}"
        )
        assert checkout["with"]["persist-credentials"] is False
    assert jobs["build"]["needs"] == "check"
    assert jobs["build"]["if"] == "needs.check.outputs.should_publish == 'true'"
    assert jobs["publish"]["needs"] == "build"
    assert jobs["publish"]["environment"] == "pypi"
    assert jobs["publish"]["permissions"] == {"id-token": "write"}
    assert WORKFLOW["concurrency"]["cancel-in-progress"] is False
