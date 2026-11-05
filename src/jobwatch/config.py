from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

Kind = Literal["greenhouse", "ashby", "lever"]
KINDS: tuple[Kind, ...] = ("greenhouse", "ashby", "lever")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_SOURCES = 50


class ConfigError(ValueError):
    """The configuration is unusable. Messages name the problem, never echo file contents."""


@dataclass(frozen=True, slots=True)
class Source:
    name: str
    kind: Kind
    token: str


def parse_config(data: Mapping[str, object]) -> tuple[Source, ...]:
    raw = data.get("source")
    if not isinstance(raw, list) or not raw:
        raise ConfigError("config needs at least one [[source]] table")
    entries = cast(list[object], raw)
    if len(entries) > MAX_SOURCES:
        raise ConfigError(f"at most {MAX_SOURCES} sources are supported")
    sources: list[Source] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ConfigError(f"source #{index} must be a table")
        table = cast(dict[str, object], entry)
        unknown = sorted(set(table) - {"name", "kind", "token"})
        if unknown:
            raise ConfigError(f"source #{index} has unknown keys: {', '.join(unknown)}")
        name, kind, token = table.get("name"), table.get("kind"), table.get("token")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise ConfigError(f"source #{index} needs a name of 1-80 characters")
        if kind not in KINDS:
            raise ConfigError(f"source #{index} kind must be one of {', '.join(KINDS)}")
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise ConfigError(f"source #{index} token must match [A-Za-z0-9_-]{{1,64}}")
        if name in seen:
            raise ConfigError(f"duplicate source name: {name}")
        seen.add(name)
        sources.append(Source(name.strip(), kind, token))
    return tuple(sources)


def load_config(path: Path) -> tuple[Source, ...]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"cannot read config file: {type(error).__name__}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError("config is not valid TOML") from error
    return parse_config(data)
