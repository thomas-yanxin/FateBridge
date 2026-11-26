"""Resolve explicit Moira provider resources without chart or clock defaults.

The source definition is Moira1.50Final, At Home Projects2004–2015, commit
9bb126fd84997aa26fed6e91b4bdf438fceb0e38. Its resource data remains external
and is not bundled or relicensed here. The historical application and Swiss
catalogue have separately recorded licensing and astronomical qualifications.

Mansion membership uses exact supplied-value circle intervals. It deliberately
does not emulate rounded Java wrap additions or qualify a modern backend as
the original Java astronomy. Calendar facts are explicit premises, not dates
inferred from a public receipt or an ordinal life palace.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from fatebridge.core.guolao.guolao_moira_rules import MoiraSourceFacts


@dataclass(frozen=True)
class MoiraMansionAnchor:
    query: str
    label: str
    correction: float


@dataclass(frozen=True)
class MoiraGodPlacement:
    branch: str
    name: str


@dataclass(frozen=True)
class MoiraProviderProfile:
    profile_id: str
    source_commit: str
    full_zodiac: tuple[str, ...]
    zodiac: tuple[str, ...]
    twelve_signs: tuple[str, ...]
    bodies: tuple[str, ...]
    anchors: tuple[MoiraMansionAnchor, ...]
    corrections: Mapping[str, float]
    selected_gods: tuple[str, ...]
    year_names: tuple[str, ...]
    stems: tuple[str, ...]
    branches: tuple[str, ...]
    year_data: Mapping[str, tuple[str, ...]]
    long_life_index: int
    long_life_starts: Mapping[str, int]
    long_life_stages: tuple[str, ...]
    year_gods: Mapping[str, tuple[MoiraGodPlacement, ...]]
    stem_gods: Mapping[str, tuple[MoiraGodPlacement, ...]]
    branch_gods: Mapping[str, tuple[MoiraGodPlacement, ...]]
    month_gods: Mapping[str, tuple[MoiraGodPlacement, ...]]
    month_hour_gods: Mapping[str, tuple[MoiraGodPlacement, ...]]
    qi_name: str
    qi_seeds: Mapping[str, tuple[str, str]]
    groups: Mapping[str, tuple[str, ...]]
    master_defaults: Mapping[str, bool]
    paired_gods: tuple[tuple[str, str], ...]
    god_requirements: Mapping[str, tuple[str, ...]]
    seasons: tuple[str, ...]
    lunar_faces: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class MoiraCalendarFacts:
    year_pillar: str | None = None
    month_pillar: str | None = None
    hour_branch: str | None = None
    lunar_day: int | None = None
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


@dataclass(frozen=True)
class MoiraMansionBoundaries:
    points: tuple[Fraction, ...]
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.points) != 28:
            raise ValueError("Moira mansion boundaries require all28 source points")
        object.__setattr__(
            self, "points", tuple(Fraction(p) % 360 for p in self.points)
        )
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


@dataclass(frozen=True)
class MoiraProviderResolution:
    facts: MoiraSourceFacts
    known_absent: tuple[str, ...]


def _source_array(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(","))


def _source_placements(value: str) -> tuple[MoiraGodPlacement, ...]:
    placements: list[MoiraGodPlacement] = []
    for entry in _source_array(value):
        branch, separator, name = entry.partition(":")
        if not separator or not branch or not name:
            raise ValueError("Moira god resource requires branch:name entries")
        placements.append(MoiraGodPlacement(branch, name))
    return tuple(placements)


def _source_enabled(
    name: str,
    defaults: Mapping[str, bool],
    pairs: tuple[tuple[str, str], ...],
) -> bool:
    if name in defaults:
        return defaults[name]
    for first, second in pairs:
        if name == second:
            return defaults.get(first, True)
    return True


def load_provider_profile(path: Path) -> MoiraProviderProfile:
    """Own external resource validation and produce one immutable profile."""
    document: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Moira provider profile must be an object")
    identity: dict[str, str] = {}
    for key in ("profile_id", "source_commit"):
        value = document.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Moira provider profile requires string {key}")
        identity[key] = value
    raw_resources = document.get("resources")
    if not isinstance(raw_resources, dict):
        raise ValueError("Moira provider profile requires resources")
    resources: dict[str, str] = {}
    for key, value in raw_resources.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(
                "Moira provider resources must have string keys and values"
            )
        resources[key] = value
    selections: dict[str, tuple[str, ...]] = {}
    for key in ("selected_gods", "selected_bodies"):
        value = document.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(f"Moira provider profile requires string list {key}")
        selections[key] = tuple(item for item in value if isinstance(item, str))

    zodiac = _source_array(resources["zodiac"])
    full_zodiac = _source_array(resources["full_zodiac"])
    twelve_signs = _source_array(resources["twelve_signs"])
    labels = _source_array(resources["full_stellar_signs"])
    names = _source_array(resources["stellar_names"])
    if len(zodiac) != 12 or len(full_zodiac) != 12 or len(twelve_signs) != 12:
        raise ValueError(
            "Moira provider profile requires its three source12-place orders"
        )
    if len(labels) != 28 or len(names) != 28:
        raise ValueError(
            "Moira provider profile requires all28 mansion labels and queries"
        )
    corrections = {name: float(resources[name]) for name in names}
    if not all(math.isfinite(value) for value in corrections.values()):
        raise ValueError("Moira source star corrections must be finite")
    anchors = tuple(
        MoiraMansionAnchor("," + name, label, corrections[name])
        for name, label in zip(names, labels)
    )

    year_names = _source_array(resources["birth_year_names"])
    stems = _source_array(resources["sky_pole_names"])
    branches = _source_array(resources["earth_pole_names"])
    year_data = {year: _source_array(resources[year]) for year in year_names}
    long_life_index = int(resources["long_life_start"]) - 1
    if len(year_names) != 60 or len(stems) != 10 or len(branches) != 12:
        raise ValueError(
            "Moira provider profile requires source60years/10stems/12branches"
        )
    if any(len(values) <= long_life_index for values in year_data.values()):
        raise ValueError(
            "Moira year resources do not contain the long-life source field"
        )
    long_life_starts: dict[str, int] = {}
    for start_record in _source_array(resources["long_life_pos"]):
        element, start = start_record.split(":", 1)
        long_life_starts[element] = int(start)
    long_life_stages = _source_array(resources["long_life_signs"])
    if len(long_life_stages) != 12:
        raise ValueError("Moira long-life cycle requires all12 source stages")

    year_gods = {
        year: _source_placements(resources[resources["star_sky_earth_key"] + year])
        for year in year_names
    }
    stem_gods = {
        stem: _source_placements(resources[resources["star_sky_key"] + stem])
        for stem in stems
    }
    branch_gods = {
        branch: _source_placements(resources[resources["star_earth_key"] + branch])
        for branch in branches
    }
    month_gods = {
        branch: _source_placements(resources[resources["star_month_key"] + branch])
        for branch in branches
    }
    month_hour_gods = {
        month
        + hour: _source_placements(
            resources[resources["star_month_hour_key"] + month + hour]
        )
        for month in branches
        for hour in branches
    }
    qi_name = resources["star_sky_qi_key"]
    qi_seeds: dict[str, tuple[str, str]] = {}
    for stem in stems:
        start, separator, target = resources[qi_name + stem].partition(":")
        if not separator or start not in zodiac or target not in zodiac:
            raise ValueError("Moira qi source requires two source palace branches")
        qi_seeds[stem] = (start, target)

    tables = (year_gods, stem_gods, branch_gods, month_gods, month_hour_gods)
    groups = {
        entry.name: _source_array(resources[entry.name])
        for table in tables
        for placements in table.values()
        for entry in placements
        if entry.name in resources
    }
    paired_values = _source_array(resources["star_equ_map"])
    if len(paired_values) % 2:
        raise ValueError("Moira source god aliases require pairs")
    paired_gods = tuple(zip(paired_values[::2], paired_values[1::2]))
    master_defaults: dict[str, bool] = {}
    for name in _source_array(resources["master_list"]):
        if name.startswith("+"):
            for entry in _source_placements(resources[name[1:]]):
                master_defaults[entry.name] = False
                for child in groups.get(entry.name, ()):
                    master_defaults[child] = False
        else:
            master_defaults[name] = False
    for name in _source_array(resources["birth_master_display_list"]):
        master_defaults[name] = True

    requirements: dict[str, set[str]] = {
        name: set() for name in selections["selected_gods"]
    }
    for table, needed in (
        (year_gods, ("year_pillar",)),
        (stem_gods, ("year_pillar",)),
        (branch_gods, ("year_pillar",)),
        (month_gods, ("month_pillar",)),
        (month_hour_gods, ("month_pillar", "hour_branch")),
    ):
        for placements in table.values():
            for entry in placements:
                generated = (entry.name,) + tuple(
                    child[1:] if child.startswith("+") else child
                    for child in groups.get(entry.name, ())
                )
                for name in generated:
                    if _source_enabled(name, master_defaults, paired_gods):
                        requirements.setdefault(name, set()).update(needed)
    for name in long_life_stages:
        if _source_enabled(name, master_defaults, paired_gods):
            requirements.setdefault(name, set()).add("year_pillar")
    if _source_enabled(qi_name, master_defaults, paired_gods):
        requirements.setdefault(qi_name, set()).update(
            ("year_pillar", "selected_luminary")
        )
    for first, second in paired_gods:
        combined = requirements.get(first, set()) | requirements.get(second, set())
        requirements.setdefault(first, set()).update(combined)
        requirements.setdefault(second, set()).update(combined)
    lunar_faces: list[tuple[str, int, int]] = []
    for number in ("1", "2"):
        start, end = _source_array(resources["lunar_face_" + number + "_range"])
        lunar_faces.append((resources["lunar_face_" + number], int(start), int(end)))

    return MoiraProviderProfile(
        profile_id=identity["profile_id"],
        source_commit=identity["source_commit"],
        full_zodiac=full_zodiac,
        zodiac=zodiac,
        twelve_signs=twelve_signs,
        bodies=selections["selected_bodies"],
        anchors=anchors,
        corrections=MappingProxyType(corrections),
        selected_gods=selections["selected_gods"],
        year_names=year_names,
        stems=stems,
        branches=branches,
        year_data=MappingProxyType(year_data),
        long_life_index=long_life_index,
        long_life_starts=MappingProxyType(long_life_starts),
        long_life_stages=long_life_stages,
        year_gods=MappingProxyType(year_gods),
        stem_gods=MappingProxyType(stem_gods),
        branch_gods=MappingProxyType(branch_gods),
        month_gods=MappingProxyType(month_gods),
        month_hour_gods=MappingProxyType(month_hour_gods),
        qi_name=qi_name,
        qi_seeds=MappingProxyType(qi_seeds),
        groups=MappingProxyType(groups),
        master_defaults=MappingProxyType(master_defaults),
        paired_gods=paired_gods,
        god_requirements=MappingProxyType(
            {
                name: tuple(sorted(requirements[name]))
                for name in selections["selected_gods"]
            }
        ),
        seasons=_source_array(resources["four_seasons"]),
        lunar_faces=tuple(lunar_faces),
    )


def resolve_source_provider_facts(
    *,
    profile: MoiraProviderProfile,
    calendar: MoiraCalendarFacts,
    longitudes: Mapping[str, float | Fraction],
    is_day: bool | None,
    mansion_boundaries: MoiraMansionBoundaries | None = None,
) -> MoiraProviderResolution:
    """Resolve the owned source namespaces from independently optional facts.

    known_absent contains full god namespace keys known to be disabled or
    without a source position. Missing prerequisites instead appear only in
    facts.unavailable. This result never overwrites a caller's LuWei table.
    """
    palaces: dict[str, str] = {}
    mansions: dict[str, str] = {}
    strings: dict[str, str | tuple[str, ...]] = {}
    booleans: dict[str, bool] = {}
    unavailable: dict[str, str] = {}
    known_absent: list[str] = []
    coordinates = {name: Fraction(value) % 360 for name, value in longitudes.items()}
    head: list[MoiraGodPlacement] = []

    def add_entries(entries: tuple[MoiraGodPlacement, ...]) -> None:
        for entry in entries:
            head.append(entry)
            for child in profile.groups.get(entry.name, ()):
                name = child[1:] if child.startswith("+") else child
                head.append(MoiraGodPlacement(entry.branch, name))

    year = calendar.year_pillar
    if year is not None:
        element = profile.year_data[year][profile.long_life_index]
        start = profile.long_life_starts[element]
        for offset, name in enumerate(profile.long_life_stages):
            head.append(
                MoiraGodPlacement(profile.twelve_signs[(start + offset) % 12], name)
            )
        add_entries(profile.year_gods[year])
        add_entries(profile.stem_gods[year[0]])
        selected_luminary = "日" if is_day else "月"
        if is_day is not None and selected_luminary in coordinates:
            stem_index = profile.stems.index(year[0])
            seed, _ = profile.qi_seeds[year[0]]
            palace_index = coordinates[selected_luminary] // 30
            shift = (palace_index - profile.zodiac.index(seed)) % 12
            shifted_stem = profile.stems[(stem_index + shift) % 10]
            _, target = profile.qi_seeds[shifted_stem]
            head.append(MoiraGodPlacement(target, profile.qi_name))
        add_entries(profile.branch_gods[year[1]])
    if calendar.month_pillar is not None:
        month = calendar.month_pillar[1]
        add_entries(profile.month_gods[month])
        if calendar.hour_branch is not None:
            add_entries(profile.month_hour_gods[month + calendar.hour_branch])

    source_palaces: dict[str, str] = {}
    for palace in profile.full_zodiac:
        for entry in head:
            if entry.branch == palace[0] and _source_enabled(
                entry.name, profile.master_defaults, profile.paired_gods
            ):
                source_palaces[entry.name] = palace
    for first, second in profile.paired_gods:
        if first in source_palaces:
            source_palaces[second] = source_palaces[first]
        elif second in source_palaces:
            source_palaces[first] = source_palaces[second]
    for name in profile.selected_gods:
        missing = []
        for requirement in profile.god_requirements[name]:
            if requirement == "year_pillar" and year is None:
                missing.append("source year pillar")
            elif requirement == "month_pillar" and calendar.month_pillar is None:
                missing.append("source month pillar")
            elif requirement == "hour_branch" and calendar.hour_branch is None:
                missing.append("source hour branch")
            elif requirement == "selected_luminary":
                if is_day is None:
                    missing.append("source day/night")
                elif ("日" if is_day else "月") not in coordinates:
                    missing.append("selected source luminary longitude")
        if missing:
            unavailable["@" + name] = "Missing " + ", ".join(missing) + " for @" + name
        elif name in source_palaces:
            palaces[name] = source_palaces[name]
        else:
            known_absent.append("@" + name)

    if calendar.month_pillar is None:
        unavailable["$月柱"] = "Source month pillar unavailable"
        for season in profile.seasons:
            unavailable["?" + season] = "Source month-pillar season unavailable"
    else:
        strings["月柱"] = calendar.month_pillar
        season_index = (
            (profile.branches.index(calendar.month_pillar[1]) - 2) % 12
        ) // 3
        for index, season in enumerate(profile.seasons):
            booleans[season] = index == season_index
    for name, start, end in profile.lunar_faces:
        if calendar.lunar_day is None:
            unavailable["?" + name] = (
                "Source lunar-calendar day unavailable for ?" + name
            )
        else:
            day = calendar.lunar_day
            booleans[name] = (
                day >= start or day <= end if start > end else start <= day <= end
            )

    for name in profile.bodies + ("身",):
        coordinate_name = "月" if name == "身" else name
        if mansion_boundaries is None:
            reason = (
                "Selected source ecliptic mansion boundaries unavailable for %" + name
            )
        elif coordinate_name not in coordinates:
            reason = "Source longitude unavailable for %" + name
        else:
            longitude = coordinates[coordinate_name]
            points = mansion_boundaries.points
            previous = points[-1]
            mansion = "?invalid?"
            for index, point in enumerate(points):
                contains = (
                    previous <= longitude < point
                    if previous <= point
                    else longitude >= previous or longitude < point
                )
                if contains:
                    mansion = profile.anchors[index - 1].label
                    break
                previous = point
            mansions[name] = mansion
            booleans[name + "宿歧"] = any(
                min((longitude - point) % 360, (point - longitude) % 360) < 1
                for point in points
            )
            continue
        unavailable["%" + name] = reason
        unavailable["?" + name + "宿歧"] = reason
    unavailable["%命"] = (
        "Ordinal life palace does not supply a source life degree/mansion"
    )
    unavailable["?命宿歧"] = "Source life degree and mansion remain unresolved"
    provenance = {
        "provider_profile_id": profile.profile_id,
        "provider_source_commit": profile.source_commit,
        "source_god_policy": "original natal table/group/master/paired-alias ordering; explicit calendar premises",
        "source_master_policy": "pinned default birth master table without saved preference overrides",
        "source_season_policy": "month-pillar branch divided into source four seasons; distinct from solar-longitude season",
        "mansion_policy": "exact supplied-value circular half-open intervals in source order; strict less than1degree",
        "mansion_reference_limit": "original Java rounded-wrap results and backend astronomy qualify separately",
        "life_degree": "not inferred; %命 remains unavailable",
        **{"calendar_" + key: value for key, value in calendar.provenance.items()},
    }
    if mansion_boundaries is not None:
        provenance.update(
            {
                "mansion_" + key: value
                for key, value in mansion_boundaries.provenance.items()
            }
        )
    return MoiraProviderResolution(
        MoiraSourceFacts(
            palaces=MappingProxyType(palaces),
            mansions=MappingProxyType(mansions),
            strings=MappingProxyType(strings),
            booleans=MappingProxyType(booleans),
            unavailable=MappingProxyType(unavailable),
            provenance=MappingProxyType(provenance),
        ),
        tuple(known_absent),
    )
