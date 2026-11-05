from __future__ import annotations

from pathlib import Path

import pytest

from jobwatch.config import ConfigError, load_config, parse_config


def src(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"name": "A", "kind": "greenhouse", "token": "a-1"}
    return {**base, **overrides}


def test_valid_config() -> None:
    sources = parse_config({"source": [src(), src(name="B", kind="lever", token="b_2")]})
    assert [s.name for s in sources] == ["A", "B"]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"source": []},
        {"source": "nope"},
        {"source": ["nope"]},
        {"source": [src(extra=1)]},
        {"source": [src(name="")]},
        {"source": [src(name="x" * 81)]},
        {"source": [src(kind="bing")]},
        {"source": [src(token="../etc")]},
        {"source": [src(token="a b")]},
        {"source": [src(token="")]},
        {"source": [src(token=7)]},
        {"source": [src(), src()]},
        {"source": [src(name=str(i)) for i in range(51)]},
    ],
)
def test_invalid_configs_are_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        parse_config(data)


def test_load_config_errors_do_not_echo_content(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("token = SECRET-LOOKING-VALUE [[", encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_config(bad)
    assert "SECRET" not in str(info.value)
    with pytest.raises(ConfigError):
        load_config(tmp_path / "missing.toml")


def test_load_config_reads_toml(tmp_path: Path) -> None:
    path = tmp_path / "s.toml"
    path.write_text('[[source]]\nname = "A"\nkind = "ashby"\ntoken = "a"\n', encoding="utf-8")
    assert load_config(path)[0].kind == "ashby"
