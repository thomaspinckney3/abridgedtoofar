"""The deployment manifests.

These assert shape, not behaviour — they cannot prove the container drops
privileges, only that the machinery for it is still wired up. The behavioural
check is test_container.py. They are here because the failure mode they catch
is a quiet revert during an unrelated edit, which no amount of runtime testing
would surface until the next deploy.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO / "requirements-web.txt"
DOCKERFILE = REPO / "Dockerfile"
ENTRYPOINT = REPO / "docker-entrypoint.sh"
FLY_TOML = REPO / "fly.toml"


def _requirement_lines() -> list[str]:
    return [line.strip() for line in REQUIREMENTS.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")]


# -- dependency pinning ----------------------------------------------------


def test_every_web_dependency_is_pinned():
    """An unpinned build ships whatever PyPI served that minute, and a bad
    release reaches production with nothing in the diff to show it."""
    unpinned = [line for line in _requirement_lines() if "==" not in line]
    assert unpinned == [], f"unpinned requirements: {unpinned}"


def test_the_pin_file_is_not_empty():
    assert len(_requirement_lines()) > 5


@pytest.mark.parametrize("package", ["fastapi", "uvicorn", "starlette"])
def test_the_web_stack_is_present_in_the_pins(package):
    names = {re.split(r"[=<>\[]", line, maxsplit=1)[0].lower()
             for line in _requirement_lines()}
    assert package in names


def test_the_image_installs_from_the_pin_file():
    dockerfile = DOCKERFILE.read_text()
    assert "requirements-web.txt" in dockerfile
    # The unpinned form this replaced.
    assert not re.search(r"pip install\s+fastapi\s", dockerfile)


def test_the_pin_file_is_copied_into_the_image():
    """Installing from a file the build context never copies fails the build,
    but only after the dependency layer has already been invalidated."""
    assert re.search(r"^COPY\b.*requirements-web\.txt", DOCKERFILE.read_text(),
                     re.MULTILINE)


# -- privilege drop --------------------------------------------------------


def test_the_image_creates_a_service_account():
    assert re.search(r"useradd.*forage", DOCKERFILE.read_text())


def test_the_image_uses_the_entrypoint():
    assert re.search(r'^ENTRYPOINT\s+\["docker-entrypoint\.sh"\]',
                     DOCKERFILE.read_text(), re.MULTILINE)


def test_the_entrypoint_chowns_the_volume_then_drops_privileges():
    script = ENTRYPOINT.read_text()
    assert "chown -R forage:forage /data" in script
    assert "exec gosu forage" in script
    # The chown has to precede the handoff, or the server starts unable to
    # write the database it was just given.
    assert script.index("chown") < script.index("exec gosu")


def test_the_entrypoint_is_executable():
    assert ENTRYPOINT.stat().st_mode & 0o111, "docker-entrypoint.sh is not executable"


# -- fly.toml --------------------------------------------------------------


@pytest.fixture(scope="module")
def fly_config() -> dict:
    return tomllib.loads(FLY_TOML.read_text())


def test_https_is_forced(fly_config):
    assert fly_config["http_service"]["force_https"] is True


def test_the_origin_allowlist_is_configured(fly_config):
    """Without it the cross-origin check falls back to comparing Origin
    against the request's own Host header."""
    hosts = fly_config["env"]["FORAGE_ALLOWED_HOSTS"].split(",")
    assert [h.strip() for h in hosts if h.strip()]


def test_strict_host_is_not_enabled_by_accident(fly_config):
    """The platform's health check arrives with the machine's address in Host,
    not the public hostname. Turning this on without accounting for that fails
    /healthz, which restarts the machine on a loop."""
    assert fly_config["env"].get("FORAGE_STRICT_HOST") in (None, "0")


def test_the_proxy_is_trusted_so_rate_limits_see_real_addresses(fly_config):
    assert fly_config["env"]["FORAGE_TRUST_PROXY"] == "1"


def test_no_secrets_are_committed_to_fly_toml(fly_config):
    """Secrets belong in the encrypted store. Anything matching these names in
    [env] is in git instead."""
    leaked = [k for k in fly_config["env"]
              if re.search(r"TOKEN|SECRET|KEY|PASSWORD", k, re.IGNORECASE)]
    assert leaked == [], f"secret-shaped keys in fly.toml [env]: {leaked}"


def test_the_sqlite_writer_stays_single_machine(fly_config):
    """The comment queue is one file on one volume: a second writer corrupts
    it. Not a security property, but it shares a config file with several."""
    assert fly_config["http_service"]["min_machines_running"] == 1
