"""Parse explicit Moira source expressions and compile their rule profile."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Namespace = Literal["@", "%", "$", "?"]
Polarity = Literal["good", "bad"]


@dataclass(frozen=True)
class Atom:
    text: str


@dataclass(frozen=True)
class Name:
    parts: tuple[Expression, ...]


@dataclass(frozen=True)
class Lookup:
    namespace: Namespace
    name: Expression


@dataclass(frozen=True)
class Index:
    value: Expression
    index: Expression


@dataclass(frozen=True)
class Negation:
    value: Expression


@dataclass(frozen=True)
class Binary:
    operator: str
    left: Expression
    right: Expression


Expression = Atom | Name | Lookup | Index | Negation | Binary


class _Parser:
    """The catalogue grammar, including nested names and eager binary nodes."""

    def __init__(self, source: str) -> None:
        self.tokens: list[str] = []
        cursor = 0
        while cursor < len(source):
            char = source[cursor]
            if char.isspace():
                cursor += 1
            elif char in "@%$?!&|=+-(){}[],":
                self.tokens.append(char)
                cursor += 1
            else:
                end = cursor
                while end < len(source) and (
                    source[end].isalnum() or source[end] in "_."
                ):
                    end += 1
                if end == cursor:
                    raise ValueError(f"Unsupported Moira catalogue token: {char}")
                self.tokens.append(source[cursor:end])
                cursor = end
        self.position = 0

    def parse(self) -> Expression:
        expression = self._binary(0)
        if self.position != len(self.tokens):
            raise ValueError("Trailing Moira catalogue expression")
        return expression

    def _binary(self, minimum: int) -> Expression:
        left = self._postfix()
        precedence = {"|": 1, "&": 2, "=": 3, "+": 4, "-": 4}
        while self.position < len(self.tokens):
            operator = self.tokens[self.position]
            priority = precedence.get(operator, -1)
            if priority < minimum:
                break
            self.position += 1
            left = Binary(operator, left, self._binary(priority + 1))
        return left

    def _postfix(self) -> Expression:
        expression = self._unary()
        if self.position < len(self.tokens) and self.tokens[self.position] == "[":
            self.position += 1
            index = self._binary(0)
            self._consume("]")
            expression = Index(expression, index)
        return expression

    def _unary(self) -> Expression:
        if self.position >= len(self.tokens):
            raise ValueError("Incomplete Moira catalogue expression")
        token = self.tokens[self.position]
        self.position += 1
        if token == "!":
            return Negation(self._unary())
        if token == "@":
            return Lookup("@", self._unary())
        if token == "%":
            return Lookup("%", self._unary())
        if token == "$":
            return Lookup("$", self._unary())
        if token == "?":
            return Lookup("?", self._unary())
        if token == "(":
            expression = self._binary(0)
            self._consume(")")
            return expression
        if token == "{":
            parts: list[Expression] = []
            while (
                self.position < len(self.tokens) and self.tokens[self.position] != "}"
            ):
                parts.append(self._postfix())
            self._consume("}")
            return Name(tuple(parts))
        if token in "}&|=+-)[],":
            raise ValueError(f"Unexpected Moira catalogue token: {token}")
        return Atom(token)

    def _consume(self, expected: str) -> None:
        if self.position >= len(self.tokens) or self.tokens[self.position] != expected:
            raise ValueError(f"Expected Moira catalogue token: {expected}")
        self.position += 1


@dataclass(frozen=True)
class CompiledRule:
    rule_id: str
    source_line: int
    condition_text: str
    condition: Expression
    priority: tuple[int, int, int]
    polarity: Polarity
    never_output: bool
    rejects: tuple[Expression, ...]

    @property
    def rank(self) -> int:
        return ((self.priority[1] << 8) + self.priority[2]) << 8


@dataclass(frozen=True)
class SourceAlias:
    name: str
    rule_id: str
    source_line: int


@dataclass(frozen=True)
class CompiledProfile:
    profile_id: str
    source_commit: str
    source_declarations: int
    rules: tuple[CompiledRule, ...]
    aliases: tuple[SourceAlias, ...]
    evaluation_order: tuple[str, ...]
    full_zodiac: tuple[str, ...]
    full_stellar_signs: tuple[str, ...]
    primitive_booleans: tuple[str, ...]
    source_strings: tuple[tuple[str, str | tuple[str, ...]], ...]
    separator: str


def _java_hashtable_order(keys: Sequence[str]) -> tuple[str, ...]:
    """Java Hashtable default construction, put, rehash and bucket enumeration."""
    buckets: list[list[tuple[int, str]]] = [[] for _ in range(11)]
    count = 0
    threshold = 8
    for key in keys:
        hash_code = 0
        encoded = key.encode("utf-16-be")
        for index in range(0, len(encoded), 2):
            unit = (encoded[index] << 8) + encoded[index + 1]
            hash_code = (31 * hash_code + unit) & 0xFFFFFFFF
        slot = (hash_code & 0x7FFFFFFF) % len(buckets)
        if any(existing == key for _, existing in buckets[slot]):
            continue
        if count >= threshold:
            old_buckets = buckets
            buckets = [[] for _ in range(2 * len(old_buckets) + 1)]
            threshold = int(len(buckets) * 0.75)
            for old_bucket in reversed(old_buckets):
                for old_hash, old_key in old_bucket:
                    new_slot = (old_hash & 0x7FFFFFFF) % len(buckets)
                    buckets[new_slot].insert(0, (old_hash, old_key))
            slot = (hash_code & 0x7FFFFFFF) % len(buckets)
        buckets[slot].insert(0, (hash_code, key))
        count += 1
    return tuple(key for bucket in reversed(buckets) for _, key in bucket)


def load_source_profile(path: Path) -> CompiledProfile:
    """Validate one external immutable source profile and compile its catalogue."""
    document: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Moira source profile must be an object")
    source: dict[str, object] = {
        key: value for key, value in document.items() if isinstance(key, str)
    }
    identity: dict[str, str] = {}
    for key in (
        "profile_id",
        "source_commit",
        "separator",
    ):
        value = source.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Moira source profile requires string {key}")
        identity[key] = value
    sequences: dict[str, tuple[str, ...]] = {}
    for key in ("full_zodiac", "full_stellar_signs", "primitive_booleans"):
        value = source.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(f"Moira source profile requires string list {key}")
        sequences[key] = tuple(item for item in value if isinstance(item, str))
    string_data = source.get("source_strings")
    if not isinstance(string_data, dict):
        raise ValueError("Moira source profile requires source_strings")
    strings: list[tuple[str, str | tuple[str, ...]]] = []
    for key, value in string_data.items():
        if not isinstance(key, str):
            raise ValueError("Moira source string key must be a string")
        if isinstance(value, str):
            strings.append((key, value))
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            strings.append(
                (key, tuple(item for item in value if isinstance(item, str)))
            )
        else:
            raise ValueError(
                "Moira source string value must be a string or ordered set"
            )
    declarations = source.get("declarations")
    if not isinstance(declarations, list):
        raise ValueError("Moira source profile requires declarations")
    rules: dict[str, CompiledRule] = {}
    aliases: list[SourceAlias] = []
    for declaration in declarations:
        if not isinstance(declaration, dict):
            raise ValueError("Moira source declaration must be an object")
        line, text = declaration.get("line"), declaration.get("text")
        if type(line) is not int or not isinstance(text, str):
            raise ValueError("Moira source declaration requires line and text")
        header, expression = "".join(text.split()).split(":", 1)
        alias = header.startswith("=")
        never = header.startswith(("+&", "-&"))
        name = header[2:] if never else header[1:]
        priority = (0, 1, 0)
        if expression.startswith("["):
            end = expression.index("]")
            parts = [int(part) for part in expression[1:end].split(".")]
            priority = (
                parts[0],
                parts[1] if len(parts) > 1 else 0,
                parts[2] if len(parts) > 2 else 0,
            )
            expression = expression[end + 1 :]
        expansions = [(name, expression)]
        if "{" in name:
            start, end = name.index("{"), name.index("}")
            expansions = []
            for item in name[start + 1 : end].split(","):
                label, _, value = item.partition("=")
                value = value if _ else label
                operand = value if alias else "{" + value + "}"
                expansions.append(
                    (
                        name[:start] + label + name[end + 1 :],
                        expression.replace("{}", operand),
                    )
                )
        for expanded_name, expanded_expression in expansions:
            expanded_name = expanded_name.lower()
            if alias:
                target = expanded_expression.replace("{", "").replace("}", "")
                aliases.append(SourceAlias(expanded_name, target, line))
                continue
            condition, *reject_texts = expanded_expression.split("~")
            rules[expanded_name] = CompiledRule(
                expanded_name,
                line,
                condition,
                _Parser(condition).parse(),
                priority,
                "good" if header[0] == "+" else "bad",
                never,
                tuple(_Parser(reject).parse() for reject in reversed(reject_texts)),
            )
    # This deliberately follows the original textual scan, not the AST's
    # semantic condition references (nested names can differ).
    for key, rule in tuple(rules.items()):
        rejects = list(rule.rejects)
        remaining = rule.condition_text
        while "?{" in remaining:
            start = remaining.rindex("?{")
            tail = remaining[start + 2 :]
            if "}" in tail:
                target = tail[: tail.index("}")]
                if target in rules:
                    rejects.append(Name((Atom(target),)))
            remaining = remaining[:start]
        rules[key] = CompiledRule(
            rule.rule_id,
            rule.source_line,
            rule.condition_text,
            rule.condition,
            rule.priority,
            rule.polarity,
            rule.never_output,
            tuple(rejects),
        )
    return CompiledProfile(
        identity["profile_id"],
        identity["source_commit"],
        len(declarations),
        tuple(rules.values()),
        tuple(aliases),
        _java_hashtable_order(tuple(rules)),
        sequences["full_zodiac"],
        sequences["full_stellar_signs"],
        sequences["primitive_booleans"],
        tuple(strings),
        identity["separator"],
    )
