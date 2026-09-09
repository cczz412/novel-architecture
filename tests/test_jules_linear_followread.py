from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import jules_linear_followread as followread


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/jules-linear-followread.yml"


def event_fixture(**overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "action": "synchronize",
        "repository": {"full_name": "cczz412/novel-architecture"},
        "pull_request": {
            "number": 208,
            "html_url": "https://github.com/cczz412/novel-architecture/pull/208",
            "title": "feat: CCZ-57 Jules 跟读",
            "body": "只关联 CCZ-57。",
            "draft": False,
            "base": {
                "ref": "main",
                "sha": "a" * 40,
                "repo": {"full_name": "cczz412/novel-architecture"},
            },
            "head": {
                "ref": "codex/issue-208-jules-actions-linear",
                "sha": "b" * 40,
                "repo": {"full_name": "cczz412/novel-architecture"},
            },
        },
    }
    for key, value in overrides.items():
        if key in event["pull_request"]:
            event["pull_request"][key] = value
        else:
            event[key] = value
    return event


def context_fixture() -> followread.PullRequestContext:
    return followread.parse_pull_request_event(event_fixture())


def completed_session(context: followread.PullRequestContext) -> dict[str, Any]:
    return {
        "name": "sessions/session-1",
        "title": followread.session_title_for(context),
        "prompt": followread.prompt_for(context),
        "state": "COMPLETED",
        "url": "https://jules.google.com/session/session-1",
        "outputs": [],
    }


def valid_report(context: followread.PullRequestContext) -> str:
    return json.dumps(
        {"verdict": "PASS", "head_sha": context.head_sha, "issues": []},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def issues_report(
    context: followread.PullRequestContext, *, title: str = "空值会覆盖已有标题"
) -> str:
    return json.dumps(
        {
            "verdict": "ISSUES",
            "head_sha": context.head_sha,
            "issues": [
                {
                    "severity": "P1",
                    "title": title,
                    "location": "tools/demo.py:42",
                    "trigger": "输入 title=null 时进入更新分支",
                    "evidence": "定向测试 test_preserves_title 断言失败",
                    "impact": "已有标题被写成空值",
                    "minimal_fix": "只在 title 非空时更新字段",
                }
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def activity_with_report(context: followread.PullRequestContext) -> dict[str, Any]:
    return {"agentMessaged": {"agentMessage": valid_report(context)}}


def test_parse_same_repository_event_and_unique_linear_identifier() -> None:
    context = context_fixture()

    assert context.repository == "cczz412/novel-architecture"
    assert context.number == 208
    assert context.linear_identifier == "CCZ-57"
    assert context.head_sha == "b" * 40


@pytest.mark.parametrize("reason", ["draft", "fork", "no-linear"])
def test_out_of_scope_pull_requests_are_skipped(reason: str) -> None:
    event = event_fixture()
    if reason == "draft":
        event["pull_request"]["draft"] = True
    elif reason == "fork":
        event["pull_request"]["head"]["repo"]["full_name"] = "outside/fork"
    else:
        event["pull_request"]["title"] = "docs: no ticket"
        event["pull_request"]["body"] = "没有任务编号"

    with pytest.raises(followread.SkipRun):
        followread.parse_pull_request_event(event)


def test_multiple_linear_identifiers_fail_before_any_api_call() -> None:
    event = event_fixture(body="同时写了 CCZ-57 和 CCZ-118")

    with pytest.raises(followread.ContractError, match="只能关联一个"):
        followread.parse_pull_request_event(event)


def test_session_payload_is_read_only_and_pins_both_shas() -> None:
    context = context_fixture()
    payload = followread.build_session_payload(context, "sources/source-1")

    assert "automationMode" not in payload
    assert "requirePlanApproval" not in payload
    assert payload["sourceContext"]["githubRepoContext"] == {
        "startingBranch": context.head_branch
    }
    assert context.base_sha in payload["prompt"]
    assert context.head_sha in payload["prompt"]
    assert context.linear_identifier in payload["title"]
    assert "禁止编辑、创建或删除文件" in payload["prompt"]
    assert "不要为了显得有用而凑问题" in payload["prompt"]
    assert '"verdict":"PASS"' in payload["prompt"]


def test_provider_configs_keep_exact_endpoints_and_write_boundary() -> None:
    jules = followread.load_json(ROOT / "config/providers/jules_api.json", "Jules 配置")
    linear = followread.load_json(
        ROOT / "config/providers/linear_graphql.json", "Linear 配置"
    )

    followread.validate_provider_configs(jules, linear)
    assert jules["dispatch_rules"]["automation_mode_must_be_omitted"] is True
    assert jules["dispatch_rules"]["send_message_allowed"] is False
    assert linear["access_rules"]["allowed_mutations"] == ["commentCreate"]
    assert linear["access_rules"]["pass_comment_allowed"] is False


class FakeHttp:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: dict[str, Any] | None = None,
        safe_attempts: int = 1,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
                "safe_attempts": safe_attempts,
            }
        )
        assert self.responses, f"没有为 {method} {url} 准备响应"
        return self.responses.pop(0)


def provider_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        followread.load_json(ROOT / "config/providers/jules_api.json", "Jules 配置"),
        followread.load_json(
            ROOT / "config/providers/linear_graphql.json", "Linear 配置"
        ),
    )


def test_jules_source_lookup_follows_pages_and_matches_owner_repo_exactly() -> None:
    jules_config, _ = provider_configs()
    http = FakeHttp(
        [
            {
                "sources": [
                    {
                        "name": "sources/other",
                        "githubRepo": {"owner": "other", "repo": "repo"},
                    }
                ],
                "nextPageToken": "page-2",
            },
            {
                "sources": [
                    {
                        "name": "sources/source-1",
                        "githubRepo": {
                            "owner": "cczz412",
                            "repo": "novel-architecture",
                        },
                    }
                ]
            },
        ]
    )
    client = followread.JulesClient("secret", jules_config, http)  # type: ignore[arg-type]

    assert client.find_source("cczz412/novel-architecture") == "sources/source-1"
    assert len(http.calls) == 2
    assert "pageToken=page-2" in http.calls[1]["url"]
    assert all(call["safe_attempts"] == 3 for call in http.calls)


def test_jules_session_creation_never_retries_or_requests_automation() -> None:
    context = context_fixture()
    jules_config, _ = provider_configs()
    response = {
        "name": "sessions/session-1",
        "id": "session-1",
        "title": followread.session_title_for(context),
    }
    http = FakeHttp([response])
    client = followread.JulesClient("secret", jules_config, http)  # type: ignore[arg-type]

    assert client.create_session(context, "sources/source-1") == response
    call = http.calls[0]
    assert call["method"] == "POST"
    assert call["safe_attempts"] == 1
    assert "automationMode" not in call["body"]
    assert "requirePlanApproval" not in call["body"]


def test_wait_for_completion_hydrates_create_response_without_state() -> None:
    context = context_fixture()
    jules_config, _ = provider_configs()
    completed = completed_session(context)
    http = FakeHttp([completed])
    client = followread.JulesClient("secret", jules_config, http)  # type: ignore[arg-type]
    sleeps: list[float] = []

    result = client.wait_for_completion(
        {"name": "sessions/session-1"},
        monotonic=lambda: 0.0,
        sleeper=sleeps.append,
    )

    assert result == completed
    assert sleeps == []
    assert http.calls == [
        {
            "method": "GET",
            "url": "https://jules.googleapis.com/v1alpha/sessions/session-1",
            "headers": {"X-Goog-Api-Key": "secret"},
            "body": None,
            "safe_attempts": 3,
        }
    ]


def test_linear_queries_paginate_but_comment_mutation_runs_once() -> None:
    _, linear_config = provider_configs()
    page_one = {
        "data": {
            "issue": {
                "id": "issue-1",
                "identifier": "CCZ-57",
                "title": "Demo",
                "comments": {
                    "nodes": [{"id": "c1", "body": "one"}],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor-2"},
                },
            }
        }
    }
    page_two = {
        "data": {
            "issue": {
                "id": "issue-1",
                "identifier": "CCZ-57",
                "title": "Demo",
                "comments": {
                    "nodes": [{"id": "c2", "body": "two"}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
            }
        }
    }
    created = {
        "data": {
            "commentCreate": {
                "success": True,
                "comment": {"id": "c3", "url": "https://linear.app/comment/c3"},
            }
        }
    }
    http = FakeHttp([page_one, page_two, created])
    client = followread.LinearClient("secret", linear_config, http)  # type: ignore[arg-type]

    issue, bodies = client.issue_and_comment_bodies("CCZ-57")
    comment = client.create_comment(issue["id"], "body")

    assert bodies == ["one", "two"]
    assert comment["id"] == "c3"
    assert [call["safe_attempts"] for call in http.calls] == [3, 3, 1]
    assert http.calls[1]["body"]["variables"]["after"] == "cursor-2"
    assert http.calls[2]["body"]["query"] == followread.COMMENT_CREATE_MUTATION


def test_linear_http_200_graphql_errors_are_failures() -> None:
    _, linear_config = provider_configs()
    http = FakeHttp([{"errors": [{"message": "permission denied"}], "data": {}}])
    client = followread.LinearClient("secret", linear_config, http)  # type: ignore[arg-type]

    with pytest.raises(followread.ExternalServiceError, match="permission denied"):
        client.graphql("query Demo { viewer { id } }", {}, safe_query=True)


def test_pass_verdict_requires_exact_sha_and_no_issues() -> None:
    context = context_fixture()
    activities = [activity_with_report(context)]

    verdict = followread.final_agent_report(context, activities)
    assert verdict == followread.ReviewVerdict(
        verdict="PASS", head_sha=context.head_sha, issues=()
    )

    activities[0]["agentMessaged"]["agentMessage"] = json.dumps(
        {"verdict": "PASS", "head_sha": "c" * 40, "issues": []}
    )
    with pytest.raises(followread.ContractError, match="Head SHA"):
        followread.final_agent_report(context, activities)


def test_issue_verdict_requires_concrete_location_and_supported_severity() -> None:
    context = context_fixture()
    activity = {"agentMessaged": {"agentMessage": issues_report(context)}}

    verdict = followread.final_agent_report(context, [activity])
    assert verdict.verdict == "ISSUES"
    assert verdict.issues[0].location == "tools/demo.py:42"

    payload = json.loads(issues_report(context))
    payload["issues"][0]["severity"] = "P3"
    activity["agentMessaged"]["agentMessage"] = json.dumps(payload)
    with pytest.raises(followread.ContractError, match="P0/P1/P2"):
        followread.final_agent_report(context, [activity])

    payload["issues"][0]["severity"] = "P2"
    payload["issues"][0]["location"] = "只是大概位置"
    activity["agentMessaged"]["agentMessage"] = json.dumps(payload)
    with pytest.raises(followread.ContractError, match="准确的相对路径和行号"):
        followread.final_agent_report(context, [activity])

    payload["issues"][0]["location"] = "tools/demo.py:42"
    payload["issues"][0]["evidence"] = "这个逻辑可能有风险"
    activity["agentMessaged"]["agentMessage"] = json.dumps(payload)
    with pytest.raises(followread.ContractError, match="猜测或纯建议"):
        followread.final_agent_report(context, [activity])


def test_change_set_or_session_output_blocks_linear_handoff() -> None:
    context = context_fixture()
    session = completed_session(context)
    change_activity = {
        "artifacts": [{"changeSet": {"gitPatch": {"unidiffPatch": "diff"}}}]
    }

    with pytest.raises(followread.ContractError, match="changeSet"):
        followread.assert_read_only_result(session, [change_activity])

    session["outputs"] = [{"pullRequest": {"url": "https://example.invalid"}}]
    with pytest.raises(followread.ContractError, match="会话输出"):
        followread.assert_read_only_result(session, [])


def test_pass_cannot_build_a_linear_comment() -> None:
    context = context_fixture()
    review = followread.ReviewVerdict(
        verdict="PASS", head_sha=context.head_sha, issues=()
    )

    with pytest.raises(followread.ContractError, match="不得写 Linear"):
        followread.build_linear_comment(context, review)


def test_issue_linear_comment_contains_only_verified_fields_and_no_mentions() -> None:
    context = context_fixture()
    activity = {
        "agentMessaged": {
            "agentMessage": issues_report(context, title="@someone 的标题会丢失")
        }
    }
    review = followread.final_agent_report(context, [activity])
    body = followread.build_linear_comment(context, review)

    assert "发现 1 个已验证问题" in body
    assert "`tools/demo.py:42`" in body
    assert "定向测试 test_preserves_title 断言失败" in body
    assert "＠someone" in body
    assert "@someone" not in body
    assert "检查范围" not in body
    assert "风险" not in body


class FakeLinear:
    def __init__(self, bodies: list[str] | None = None) -> None:
        self.bodies = list(bodies or [])
        self.created: list[tuple[str, str]] = []
        self.read_count = 0

    def issue_and_comment_bodies(
        self, identifier: str
    ) -> tuple[dict[str, Any], list[str]]:
        self.read_count += 1
        return {
            "id": "linear-internal-id",
            "identifier": identifier,
            "title": "Demo",
        }, list(self.bodies)

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        self.created.append((issue_id, body))
        self.bodies.append(body)
        return {"id": "comment-1", "url": "https://linear.app/ccz/issue/CCZ-57#comment"}


class FakeJules:
    def __init__(
        self,
        context: followread.PullRequestContext,
        *,
        existing: bool = False,
        activities: list[dict[str, Any]] | None = None,
    ) -> None:
        self.context = context
        self.session = completed_session(context)
        self.existing = existing
        self.activities = activities or [activity_with_report(context)]
        self.find_count = 0
        self.create_count = 0

    def find_session(self, title: str) -> dict[str, Any] | None:
        self.find_count += 1
        assert title == followread.session_title_for(self.context)
        return self.session if self.existing else None

    def find_source(self, repository: str) -> str:
        assert repository == self.context.repository
        return "sources/source-1"

    def create_session(
        self,
        context: followread.PullRequestContext,
        source_name: str,
    ) -> dict[str, Any]:
        assert context == self.context
        assert source_name == "sources/source-1"
        self.create_count += 1
        return self.session

    def wait_for_completion(
        self,
        session: dict[str, Any],
        *,
        monotonic: Any,
        sleeper: Any,
    ) -> dict[str, Any]:
        assert session == self.session
        return self.session

    def list_activities(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        assert session == self.session
        return self.activities


def test_duplicate_marker_skips_jules_and_linear_mutation() -> None:
    context = context_fixture()
    linear = FakeLinear([f"旧评论\n{followread.marker_for(context)}"])
    jules = FakeJules(context)

    result = followread.execute_pipeline(context, jules, linear)  # type: ignore[arg-type]

    assert result.status == "duplicate"
    assert jules.find_count == 0
    assert linear.created == []


def test_successful_pipeline_reuses_session_and_posts_once() -> None:
    context = context_fixture()
    linear = FakeLinear()
    jules = FakeJules(context, existing=True)

    result = followread.execute_pipeline(context, jules, linear)  # type: ignore[arg-type]

    assert result.status == "pass"
    assert result.verdict == "PASS"
    assert jules.create_count == 0
    assert linear.read_count == 1
    assert linear.created == []


def test_verified_issue_posts_details_and_marks_pipeline_as_issues() -> None:
    context = context_fixture()
    linear = FakeLinear()
    activity = {"agentMessaged": {"agentMessage": issues_report(context)}}
    jules = FakeJules(context, activities=[activity])

    result = followread.execute_pipeline(context, jules, linear)  # type: ignore[arg-type]

    assert result.status == "issues"
    assert result.verdict == "ISSUES"
    assert len(linear.created) == 1
    assert "[P1] 空值会覆盖已有标题" in linear.created[0][1]


def test_incomplete_jules_report_never_creates_linear_comment() -> None:
    context = context_fixture()
    linear = FakeLinear()
    bad_activity = {"agentMessaged": {"agentMessage": "可能有风险，建议补测试"}}
    jules = FakeJules(context, activities=[bad_activity])

    with pytest.raises(followread.ContractError, match="不是单个 JSON"):
        followread.execute_pipeline(context, jules, linear)  # type: ignore[arg-type]
    assert linear.created == []


def test_retired_workflow_cannot_dispatch_jules_or_write_linear() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "on:\n  workflow_dispatch:\n" in raw
    assert "pull_request" not in raw
    assert "if: ${{ false }}" in raw
    assert "permissions: {}" in raw
    assert "secrets." not in raw
    assert "uses:" not in raw
    assert "jules_linear_followread.py" not in raw

    config = followread.load_json(ROOT / "config/providers/jules_api.json", "Jules 配置")
    assert config["enabled_by_default"] is False
    assert config["status"] == "retired_replaced_by_codex_native_github_review"
    assert config["replacement"]["linear_output"] == "link_only"


def test_check_command_needs_no_secret_and_makes_no_network_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event_fixture()), encoding="utf-8")

    assert followread.main(["check", "--event-file", str(event_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "READY"
    assert payload["required_secrets"] == ["JULES_API_KEY", "LINEAR_API_KEY"]
