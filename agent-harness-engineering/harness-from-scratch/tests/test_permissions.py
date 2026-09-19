"""Policy decides on the proposal, before anything runs."""

import pytest

from harness.permissions import Decision, Policy


def test_read_only_tools_never_need_permission():
    policy = Policy(mode=Decision.DENY)

    assert policy.check("read_file", {"path": "x"}).allowed
    assert policy.check("list_files", {"path": "."}).allowed


def test_deny_mode_refuses_writes():
    policy = Policy(mode=Decision.DENY)

    verdict = policy.check("write_file", {"path": "x", "content": "y"})

    assert not verdict.allowed
    assert verdict.decision is Decision.DENY


def test_allow_mode_permits_writes():
    policy = Policy(mode=Decision.ALLOW)

    assert policy.check("write_file", {"path": "x", "content": "y"}).allowed


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -fr ~/projects",
        "sudo rm -rf --no-preserve-root /",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
        "shutdown -h now",
        "git push --force origin main",
    ],
)
def test_destructive_commands_are_refused_even_in_allow_mode(command):
    policy = Policy(mode=Decision.ALLOW)

    verdict = policy.check("run_bash", {"command": command})

    assert not verdict.allowed, f"{command!r} should have been refused"
    assert "destructive" in verdict.reason


def test_ordinary_commands_survive_the_deny_list():
    policy = Policy(mode=Decision.ALLOW)

    assert policy.check("run_bash", {"command": "ls -la"}).allowed
    assert policy.check("run_bash", {"command": "git status"}).allowed
    assert policy.check("run_bash", {"command": "pytest -q"}).allowed


def test_ask_mode_consults_the_confirmer():
    asked = []

    def confirm(tool, args, summary):
        asked.append(summary)
        return True

    policy = Policy(mode=Decision.ASK, confirm=confirm)

    assert policy.check("run_bash", {"command": "ls"}).allowed
    assert asked == ["run: ls"]


def test_ask_mode_honours_a_refusal():
    policy = Policy(mode=Decision.ASK, confirm=lambda *_: False)

    verdict = policy.check("write_file", {"path": "x", "content": "y"})

    assert not verdict.allowed
    assert "declined" in verdict.reason


def test_ask_mode_without_a_confirmer_denies_rather_than_assuming():
    policy = Policy(mode=Decision.ASK, confirm=None)

    verdict = policy.check("run_bash", {"command": "ls"})

    assert not verdict.allowed
