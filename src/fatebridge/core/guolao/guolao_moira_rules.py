"""Evaluate a supplied, versioned Moira rule profile without chart defaults.

This independently written evaluator implements the expression subset used by
Moira1.50Final's style catalogue. The authored catalogue is supplied separately;
it is not bundled or relicensed by this module. Original semantic references:
At Home Projects, Copyright2004–2015, RuleEntry/RuleParse/EvalRule at commit
9bb126fd84997aa26fed6e91b4bdf438fceb0e38, distributed GPLv2-or-later.

Source conditions, canonical evaluation state, suppression and presentation are
separate. Unavailable native facts never become false source facts. No result
certifies a classical edition, complete natal astronomy or predictive efficacy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence, TypedDict

from fatebridge.core.guolao.guolao_moira_profile import (
    Atom,
    Binary,
    CompiledProfile,
    CompiledRule,
    Expression,
    Index,
    Lookup,
    Name,
    Namespace,
    Negation,
    Polarity,
)
from fatebridge.core.guolao.guolao_moira_profile import SourceAlias as SourceAlias
from fatebridge.core.guolao.guolao_moira_profile import (
    load_source_profile as load_source_profile,
)

RawState = Literal["uncomputed", "evaluating", "computed"]
ConditionStatus = Literal["true", "false", "unknown", "undefined", "uncomputed"]
Visibility = Literal[
    "active", "suppressed", "unknown", "inactive", "internal", "uncomputed"
]


@dataclass(frozen=True)
class UnknownValue:
    facts: tuple[str, ...]


RuleValue = str | tuple[str, ...] | UnknownValue | None


class _ExpressionAbort(Exception):
    """An original expression failure caught at its rule/reject boundary."""


@dataclass(frozen=True)
class MoiraSourceFacts:
    palaces: Mapping[str, str] = field(default_factory=dict)
    mansions: Mapping[str, str] = field(default_factory=dict)
    strings: Mapping[str, str | tuple[str, ...]] = field(default_factory=dict)
    booleans: Mapping[str, bool] = field(default_factory=dict)
    unavailable: Mapping[str, str] = field(default_factory=dict)
    provenance: Mapping[str, str] = field(default_factory=dict)
    male: bool | None = None


class RuleRecord(TypedDict):
    rule_id: str
    source_line: int
    polarity: Polarity
    priority: list[int]
    never_output: bool
    raw_state: RawState
    value_status: str
    value: str | list[str] | None
    condition_status: ConditionStatus
    condition_value: bool | None
    hidden: bool
    suppressed_by: list[str]
    possibly_suppressed_by: list[str]
    visibility: Visibility
    missing_facts: list[str]
    undefined_symbols: list[str]
    evaluation_errors: list[str]


class AliasRecord(TypedDict):
    name: str
    rule_id: str
    source_line: int
    status: str
    visible: bool | None


class EvaluationCounts(TypedDict):
    source_declarations: int
    predicate_rules: int
    aliases: int
    evaluated: int
    uncomputed: int
    active: int
    suppressed: int
    unknown_conditions: int
    unresolved_visibility: int
    undefined_symbols: int


class EvaluationRecord(TypedDict):
    profile_id: str
    source_commit: str
    source_property_sha256: str
    scope: str
    fact_provenance: dict[str, str]
    counts: EvaluationCounts
    rules: list[RuleRecord]
    aliases: list[AliasRecord]


class PatternInputs(TypedDict):
    source_rule_id: str
    source_line: int
    condition: str


class PatternEvidence(TypedDict):
    model_id: str
    granularity: str
    inputs: PatternInputs
    condition_satisfied: bool
    classical_acceptance: bool


class PatternRecord(TypedDict):
    name: str
    level: Polarity
    source: str
    dsl: str
    detail: str
    rule_id: str
    evidence: PatternEvidence


@dataclass
class _RuleState:
    raw_state: RawState = "uncomputed"
    value: RuleValue = None
    hidden: bool = False
    suppressed_by: list[str] = field(default_factory=list)
    missing_facts: set[str] = field(default_factory=set)
    undefined_symbols: set[str] = field(default_factory=set)
    evaluation_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActivePattern:
    name: str
    rule: CompiledRule


@dataclass(frozen=True)
class MoiraEvaluation:
    profile: CompiledProfile
    fact_provenance: tuple[tuple[str, str], ...]
    rules: tuple[RuleRecord, ...]
    aliases: tuple[AliasRecord, ...]
    patterns: tuple[ActivePattern, ...]

    def to_record(self) -> EvaluationRecord:
        return {
            "profile_id": self.profile.profile_id,
            "source_commit": self.profile.source_commit,
            "source_property_sha256": self.profile.source_property_sha256,
            "scope": "complete_source_catalogue_with_fact_specific_unknowns_not_classical_acceptance",
            "fact_provenance": dict(self.fact_provenance),
            "counts": {
                "source_declarations": self.profile.source_declarations,
                "predicate_rules": len(self.rules),
                "aliases": len(self.aliases),
                "evaluated": sum(row["raw_state"] == "computed" for row in self.rules),
                "uncomputed": sum(
                    row["raw_state"] == "uncomputed" for row in self.rules
                ),
                "active": sum(row["visibility"] == "active" for row in self.rules),
                "suppressed": sum(
                    row["visibility"] == "suppressed" for row in self.rules
                ),
                "unknown_conditions": sum(
                    row["condition_status"] == "unknown" for row in self.rules
                ),
                "unresolved_visibility": sum(
                    row["visibility"] == "unknown" for row in self.rules
                ),
                "undefined_symbols": len(
                    {name for row in self.rules for name in row["undefined_symbols"]}
                ),
            },
            "rules": [row.copy() for row in self.rules],
            "aliases": [row.copy() for row in self.aliases],
        }


class _Evaluation:
    def __init__(
        self, profile: CompiledProfile, facts: MoiraSourceFacts, display_level: int
    ) -> None:
        self.profile = profile
        self.facts = facts
        self.display_level = display_level
        self.rules = {rule.rule_id: rule for rule in profile.rules}
        self.states = {rule.rule_id: _RuleState() for rule in profile.rules}
        self.aliases = {alias.rule_id: alias.name for alias in profile.aliases}
        self.source_strings = dict(profile.source_strings)
        self.rejected_aliases: dict[str, str] = {}
        self.unresolved_rejects: set[str] = set()

    def _string(self, value: RuleValue) -> str:
        if isinstance(value, str):
            return value
        else:
            pass
        if isinstance(value, tuple):
            return self.profile.separator.join(value)
        else:
            pass
        return ""

    def _unknown(self, values: Sequence[RuleValue]) -> UnknownValue | None:
        names = {
            name
            for value in values
            if isinstance(value, UnknownValue)
            for name in value.facts
        }
        return UnknownValue(tuple(sorted(names))) if names else None

    def _lookup(self, namespace: Namespace, name: str, current: str) -> RuleValue:
        key = namespace + name
        state = self.states[current]
        if namespace == "?":
            if name in self.facts.booleans:
                return "t" if self.facts.booleans[name] else "f"
            else:
                pass
            if key in self.facts.unavailable:
                reason = self.facts.unavailable[key]
                state.missing_facts.add(reason)
                return UnknownValue((reason,))
            else:
                pass
            if name in self.rules:
                result = self.rule_value(name, check_level=False)
                state.missing_facts.update(self.states[name].missing_facts)
                state.undefined_symbols.update(self.states[name].undefined_symbols)
                return result
            else:
                pass
            if name not in self.profile.primitive_booleans:
                state.undefined_symbols.add(key)
            else:
                pass
            return "f"
        else:
            values: Mapping[str, str | tuple[str, ...]]
            if namespace == "@":
                values = self.facts.palaces
            elif namespace == "%":
                values = self.facts.mansions
            else:
                values = self.facts.strings
            if name in values:
                return values[name]
            else:
                pass
            if namespace == "$" and name in self.source_strings:
                return self.source_strings[name]
            else:
                pass
        if key in self.facts.unavailable:
            reason = self.facts.unavailable[key]
            state.missing_facts.add(reason)
            return UnknownValue((reason,))
        else:
            pass
        state.undefined_symbols.add(key)
        raise _ExpressionAbort(f"{key} not defined")

    def expression_value(self, expression: Expression, current: str) -> RuleValue:
        if isinstance(expression, Atom):
            return expression.text
        else:
            pass
        if isinstance(expression, Name):
            parts = [self.expression_value(part, current) for part in expression.parts]
            if len(parts) == 1:
                return parts[0]
            else:
                pass
            unknown = self._unknown(parts)
            return unknown if unknown else "".join(self._string(part) for part in parts)
        else:
            pass
        if isinstance(expression, Lookup):
            name = self.expression_value(expression.name, current)
            if isinstance(name, UnknownValue):
                return name
            else:
                pass
            return self._lookup(expression.namespace, self._string(name), current)
        else:
            pass
        if isinstance(expression, Index):
            value = self.expression_value(expression.value, current)
            index_value = self.expression_value(expression.index, current)
            unknown = self._unknown((value, index_value))
            if unknown:
                return unknown
            else:
                pass
            index = int(self._string(index_value)[0])
            if isinstance(value, str):
                return value[index] if 0 <= index < len(value) else ()
            else:
                pass
            if isinstance(value, tuple):
                return tuple(
                    dict.fromkeys(
                        item[index] for item in value if 0 <= index < len(item)
                    )
                )
            else:
                pass
            raise _ExpressionAbort("null index argument")
        else:
            pass
        if isinstance(expression, Negation):
            value = self.expression_value(expression.value, current)
            if isinstance(value, UnknownValue):
                return value
            else:
                pass
            return "f" if self._string(value) == "t" else "t"
        else:
            pass
        left = self.expression_value(expression.left, current)
        right = self.expression_value(expression.right, current)
        # Both operands have already been evaluated, as in the original parser.
        unknown = self._unknown((left, right))
        if expression.operator == "&":
            if self._string(left) == "f" or self._string(right) == "f":
                return "f"
            else:
                pass
            if unknown:
                return unknown
            else:
                pass
            return (
                "t" if self._string(left) == "t" and self._string(right) == "t" else "f"
            )
        else:
            pass
        if expression.operator == "|":
            if self._string(left) == "t" or self._string(right) == "t":
                return "t"
            else:
                pass
            if unknown:
                return unknown
            else:
                pass
            return "f"
        else:
            pass
        if unknown:
            return unknown
        else:
            pass
        if expression.operator == "=":
            if left is None or right is None:
                raise _ExpressionAbort("null containment argument")
            else:
                pass
            left_set = (left,) if isinstance(left, str) else left
            right_set = (right,) if isinstance(right, str) else right
            if isinstance(left_set, tuple) and isinstance(right_set, tuple):
                return "t" if any(item in right_set for item in left_set) else "f"
            else:
                pass
            return "f"
        else:
            pass
        first = self._string(left)
        shift = int(self._string(right)[0])
        if expression.operator == "-":
            shift = -shift
        else:
            pass
        if first in self.profile.full_zodiac and -6 <= shift <= 6:
            circle = self.profile.full_zodiac
        elif first in self.profile.full_stellar_signs and -14 <= shift <= 14:
            circle = self.profile.full_stellar_signs
        else:
            raise _ExpressionAbort(f"{first} is not a legal shifted value")
        return circle[(circle.index(first) + shift) % len(circle)]

    def rule_value(self, rule_id: str, *, check_level: bool) -> RuleValue:
        state, rule = self.states[rule_id], self.rules[rule_id]
        if state.raw_state != "uncomputed":
            return state.value
        else:
            pass
        if check_level and (state.hidden or rule.priority[0] < self.display_level):
            return state.value
        else:
            pass
        state.raw_state = "evaluating"
        try:
            state.value = self.expression_value(rule.condition, rule_id)
        except _ExpressionAbort as error:
            state.value = None
            state.evaluation_errors.append(str(error))
        state.raw_state = "computed"
        if self._string(state.value) == "t":
            self.reject(rule)
        else:
            pass
        return state.value

    def reject(self, source: CompiledRule) -> None:
        for expression in source.rejects:
            try:
                value = self.expression_value(expression, source.rule_id)
            except _ExpressionAbort as error:
                self.states[source.rule_id].evaluation_errors.append(str(error))
                continue
            if isinstance(value, UnknownValue):
                self.unresolved_rejects.add(source.rule_id)
                continue
            else:
                pass
            key = self._string(value)
            target = self.rules.get(key)
            if target is None:
                self.rejected_aliases.setdefault(key, source.rule_id)
                continue
            else:
                pass
            if not self.may_reject(source, target):
                continue
            else:
                pass
            state = self.states[key]
            if not state.hidden:
                state.hidden = True
                state.suppressed_by.append(source.rule_id)
                self.reject(target)
            else:
                pass

    @staticmethod
    def may_reject(source: CompiledRule, target: CompiledRule) -> bool:
        return target.priority[0] < source.priority[0] or (
            target.priority[0] == source.priority[0]
            and (target.rank >> 8) <= (source.rank >> 8)
        )

    def possible_strings(self, expression: Expression) -> set[str]:
        """Finite source-value domains for unresolved rejection targets only.

        This does not evaluate conditions or mutate canonical states. Unknown
        coordinates range over the source's complete finite palace/mansion set.
        """
        if isinstance(expression, Atom):
            return {expression.text}
        else:
            pass
        if isinstance(expression, Name):
            names = {""}
            for part in expression.parts:
                names = {
                    prefix + suffix
                    for prefix in names
                    for suffix in self.possible_strings(part)
                }
            return names
        else:
            pass
        if isinstance(expression, Lookup):
            values: set[str] = set()
            for name in self.possible_strings(expression.name):
                if expression.namespace == "@":
                    values.update(
                        (self.facts.palaces[name],)
                        if name in self.facts.palaces
                        else self.profile.full_zodiac
                    )
                elif expression.namespace == "%":
                    values.update(
                        (self.facts.mansions[name],)
                        if name in self.facts.mansions
                        else self.profile.full_stellar_signs
                    )
                elif expression.namespace == "$":
                    item = self.facts.strings.get(name, self.source_strings.get(name))
                    if isinstance(item, str):
                        values.add(item)
                    elif isinstance(item, tuple):
                        values.add(self.profile.separator.join(item))
                    else:
                        # Runtime catalogue rejection names use ruler and
                        # mansion namespaces. This branch remains conservative.
                        values.update(self.rules)
                else:
                    values.update(("t", "f"))
            return values
        else:
            pass
        if isinstance(expression, Index):
            return {
                value[int(index[0])]
                for value in self.possible_strings(expression.value)
                for index in self.possible_strings(expression.index)
                if index and index[0].isdigit() and int(index[0]) < len(value)
            }
        else:
            pass
        if isinstance(expression, Negation):
            return {"t", "f"}
        else:
            pass
        if expression.operator in ("&", "|", "="):
            return {"t", "f"}
        else:
            pass
        results: set[str] = set()
        for value in self.possible_strings(expression.left):
            for amount in self.possible_strings(expression.right):
                shift = int(amount[0]) * (-1 if expression.operator == "-" else 1)
                circle = (
                    self.profile.full_zodiac
                    if value in self.profile.full_zodiac
                    else self.profile.full_stellar_signs
                )
                if value in circle:
                    results.add(circle[(circle.index(value) + shift) % len(circle)])
                else:
                    pass
        return results

    def possible_suppression(self) -> tuple[dict[str, set[str]], set[str]]:
        possible: dict[str, set[str]] = {key: set() for key in self.rules}
        aliases: set[str] = set()
        roots = {
            key
            for key, state in self.states.items()
            if isinstance(state.value, UnknownValue)
        } | self.unresolved_rejects
        for root in roots:
            visited: set[str] = set()
            pending = [root]
            while pending:
                key = pending.pop()
                if key in visited:
                    continue
                else:
                    pass
                visited.add(key)
                source = self.rules[key]
                for expression in source.rejects:
                    for target_name in self.possible_strings(expression):
                        target = self.rules.get(target_name)
                        if target is None:
                            aliases.add(target_name)
                        elif self.may_reject(source, target):
                            possible[target_name].add(root)
                            pending.append(target_name)
                        else:
                            pass
        return possible, aliases


def evaluate_source_profile(
    facts: MoiraSourceFacts,
    *,
    profile: CompiledProfile,
    display_level: int = 0,
    fill_max_styles: int | None = None,
) -> MoiraEvaluation:
    """Run one canonical source-order evaluation, then a read-only projection.

    No diagnostic truth queries are appended to the canonical run. In particular
    a hidden uncomputed node remains uncomputed in every returned raw field.
    """
    evaluation = _Evaluation(profile, facts, display_level)
    for rule_id in profile.evaluation_order:
        evaluation.rule_value(rule_id, check_level=True)
    possible, possible_aliases = evaluation.possible_suppression()
    records: dict[str, RuleRecord] = {}
    for rule in profile.rules:
        state = evaluation.states[rule.rule_id]
        value = state.value
        if state.raw_state == "uncomputed":
            value_status = "uncomputed"
            condition_status: ConditionStatus = "uncomputed"
            condition_value: bool | None = None
        elif isinstance(value, UnknownValue):
            value_status = "unknown"
            condition_status = "unknown"
            condition_value = None
        else:
            value_status = "null" if value is None else "known"
            condition_value = evaluation._string(value) == "t"
            condition_status = "true" if condition_value else "false"
        visibility: Visibility
        if state.hidden:
            visibility = "suppressed"
        elif state.raw_state == "uncomputed":
            visibility = "uncomputed"
        elif condition_value is None:
            visibility = "unknown"
        elif not condition_value or rule.priority[0] < display_level:
            visibility = "inactive"
        elif rule.never_output and rule.rule_id not in evaluation.aliases:
            visibility = "internal"
        elif possible[rule.rule_id]:
            visibility = "unknown"
        else:
            visibility = "active"
        record_value: str | list[str] | None
        if isinstance(value, str):
            record_value = value
        elif isinstance(value, tuple):
            record_value = list(value)
        else:
            record_value = None
        records[rule.rule_id] = {
            "rule_id": rule.rule_id,
            "source_line": rule.source_line,
            "polarity": rule.polarity,
            "priority": list(rule.priority),
            "never_output": rule.never_output,
            "raw_state": state.raw_state,
            "value_status": value_status,
            "value": record_value,
            "condition_status": condition_status,
            "condition_value": condition_value,
            "hidden": state.hidden,
            "suppressed_by": list(state.suppressed_by),
            "possibly_suppressed_by": sorted(possible[rule.rule_id]),
            "visibility": visibility,
            "missing_facts": sorted(state.missing_facts),
            "undefined_symbols": sorted(state.undefined_symbols),
            "evaluation_errors": list(state.evaluation_errors),
        }
    patterns: list[ActivePattern] = []
    displayed: dict[str, str] = {}
    style_counts: dict[Polarity, int] = {"good": 0, "bad": 0}
    ordered = sorted(
        profile.rules,
        key=lambda rule: (
            -rule.priority[0],
            -rule.rank,
            rule.rule_id.encode("utf-16-be"),
        ),
    )
    for rule in ordered:
        record = records[rule.rule_id]
        if (
            record["visibility"] not in ("active", "unknown")
            or record["condition_value"] is not True
        ):
            continue
        else:
            pass
        name = evaluation.aliases.get(rule.rule_id, rule.rule_id)
        if rule.rule_id in evaluation.aliases and name in evaluation.rejected_aliases:
            record["visibility"] = "suppressed"
            record["suppressed_by"].append(evaluation.rejected_aliases[name])
            continue
        else:
            pass
        if name in possible_aliases:
            record["visibility"] = "unknown"
        else:
            pass
        if facts.male is None and "妻" in name:
            record["missing_facts"].append(
                "?male: source display remapping unavailable"
            )
            record["visibility"] = "unknown"
        elif facts.male is False:
            name = name.replace("妻", "夫")
        else:
            pass
        star = name.rfind("*")
        if star > 0:
            name = name[:star]
        else:
            pass
        if record["visibility"] != "active":
            continue
        else:
            pass
        if (
            fill_max_styles is not None
            and rule.priority[0] == display_level
            and rule.rank < 1 << 16
            and style_counts[rule.polarity] >= fill_max_styles
        ):
            record["visibility"] = "inactive"
            continue
        else:
            pass
        style_counts[rule.polarity] += 1
        displayed[rule.rule_id] = name
        patterns.append(ActivePattern(name, rule))
    aliases: list[AliasRecord] = []
    for alias in profile.aliases:
        alias_target = records.get(alias.rule_id)
        visible: bool | None
        if alias_target is None:
            status, visible = "undefined", False
        elif evaluation.aliases.get(alias.rule_id) != alias.name:
            status, visible = "inactive", False
        else:
            status = alias_target["visibility"]
            visible = None if status == "unknown" else alias.rule_id in displayed
        aliases.append(
            {
                "name": alias.name,
                "rule_id": alias.rule_id,
                "source_line": alias.source_line,
                "status": status,
                "visible": visible,
            }
        )
    return MoiraEvaluation(
        profile,
        tuple(facts.provenance.items()),
        tuple(records[rule.rule_id] for rule in profile.rules),
        tuple(aliases),
        tuple(patterns),
    )


def pattern_records(evaluation: MoiraEvaluation) -> list[PatternRecord]:
    """Project confirmed source survivors without reconstructing their inputs."""
    result: list[PatternRecord] = []
    for pattern in evaluation.patterns:
        rule = pattern.rule
        result.append(
            {
                "name": pattern.name,
                "level": rule.polarity,
                "source": evaluation.profile.source_url,
                "dsl": rule.condition_text,
                "detail": "具名Moira软件条件成立，并通过本次来源覆盖图；原典格局未验收。",
                "rule_id": rule.rule_id,
                "evidence": {
                    "model_id": evaluation.profile.profile_id,
                    "granularity": "source_namespaces",
                    "inputs": {
                        "source_rule_id": rule.rule_id,
                        "source_line": rule.source_line,
                        "condition": rule.condition_text,
                    },
                    "condition_satisfied": True,
                    "classical_acceptance": False,
                },
            }
        )
    return result
