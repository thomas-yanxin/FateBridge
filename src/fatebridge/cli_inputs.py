"""Load CLI input files and check reusable subject fields before dispatch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError
from pydantic.fields import FieldInfo

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.services.tool_catalog import CATALOG

PROFILE_PERSON_FIELDS = (
    "name",
    "gender",
    "birth_year",
    "birth_month",
    "birth_day",
    "birth_hour",
    "birth_minute",
    "birth_place",
    "birth_longitude",
    "birth_latitude",
    "birth_timezone",
    "use_true_solar_time",
)
PROFILE_REQUIRED_FIELDS = ("birth_year", "birth_month", "birth_day", "birth_hour")


def _parse_json_subject(text: str, path: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"subject 档案 {path} 不是合法 JSON：{error}") from error


def _parse_yaml_subject(text: str, path: str) -> object:
    try:
        import yaml  # note (optional dependency): Only YAML input needs PyYAML.
    except ImportError as error:
        raise ValueError(
            f"解析 YAML subject 档案 {path} 需要 pyyaml；请用 uv 为当前环境安装 pyyaml "
            "或改用 JSON 档案。"
        ) from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError(f"subject 档案 {path} 不是合法 YAML：{error}") from error


def _load_subject_file(path: str) -> dict[str, object]:
    """Read one raw subject mapping for later request validation."""
    file_path = Path(path).expanduser()
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"无法读取 subject 档案 {path}：{error}") from error

    suffix = file_path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        subject: object = _parse_yaml_subject(text, path)
    elif suffix == ".json":
        subject = _parse_json_subject(text, path)
    else:
        try:
            subject = json.loads(text)
        except json.JSONDecodeError:
            subject = _parse_yaml_subject(text, path)

    if not isinstance(subject, dict):
        raise ValueError(
            f"subject 档案 {path} 必须是键值映射（字段名→值），"
            f"实际得到 {type(subject).__name__}"
        )
    else:
        pass
    return subject


def preload_subject(
    argv: list[str] | None,
) -> dict[str, object] | None:
    """Load file defaults before argparse checks required tool flags."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--subject-file", dest="subject_file", default=None)
    try:
        pre_args, _ = pre.parse_known_args(argv)
    except SystemExit:
        # note (argparse): Let the main parse emit its JSON usage error.
        return None
    path = pre_args.subject_file
    if not path:
        return None
    else:
        pass
    return _load_subject_file(path)


def preload_request(argv: list[str] | None) -> dict[str, object] | None:
    """Load a complete JSON request for subsequent model validation."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--request-file", default=None)
    try:
        args, _ = pre.parse_known_args(argv)
    except SystemExit:
        return None
    if not args.request_file:
        return None
    else:
        pass
    try:
        data = json.loads(
            Path(args.request_file).expanduser().read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("request-file 必须为可读的合法 JSON 文件") from exc
    if not isinstance(data, dict):
        raise ValueError("request-file 顶层必须是 JSON 对象")
    else:
        pass
    return data


def profile_field_objects() -> dict[str, FieldInfo]:
    """Resolve each shared person field to a model field object from a core spec."""
    core = ("bazi_birth", "ziwei_birth", "astro_chart")
    specs = [s for s in CATALOG if s.key in core]
    resolved: dict[str, FieldInfo] = {}
    for name in PROFILE_PERSON_FIELDS:
        for spec in specs:
            field = spec.request_model.model_fields.get(name)
            if field is not None:
                resolved[name] = field
                break
            else:
                pass
    return resolved


def validate_subject_fields(
    subject_data: dict[str, object] | None, specs: list[ToolSpec]
) -> None:
    """Reject keys outside the chosen requests and shared person fields."""
    if subject_data is None:
        return
    else:
        pass
    allowed = set(profile_field_objects())
    for spec in specs:
        allowed.update(spec.request_model.model_fields)
    unexpected = [key for key in subject_data if key not in allowed]
    if unexpected:
        raise ValidationError.from_exception_data(
            "SubjectProfile",
            [
                {"type": "extra_forbidden", "loc": (key,), "input": subject_data[key]}
                for key in unexpected
            ],
        )
    else:
        pass
