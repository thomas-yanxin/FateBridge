"""Check complete recorded source-ID resolution without an engine import."""


def verify(result, expected_model, allowed_hashes):
    profile = result["chart"]["params"]["chart_profile"]
    if profile["ephemeris_model"] != expected_model:
        raise ValueError("Actual backend differs")
    source = profile.get("physical_ephemeris_source")
    if not isinstance(source, dict):
        raise ValueError("Physical source receipt missing")
    if source["has_unidentified_sources"] or source["accuracy_certified"] is not False:
        raise ValueError("Source identity unknown or promoted to accuracy")
    files = source["files"]
    ids = {f["id"] for f in files}
    if not ids or len(ids) != len(files):
        raise ValueError("Physical source files absent/duplicated")
    for file in files:
        if file["sha256"] not in allowed_hashes:
            raise ValueError("Physical file differs from frozen data")
        prefix = "jpl" if expected_model == "jpl" else "se1"
        if file["id"] != f"{prefix}:{file['slot']}:{file['sha256']}":
            raise ValueError("File identifier does not bind actual bytes/slot")
    factors = {
        "Sun",
        "Moon",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
    }
    if set(source["by_factor"]) != factors:
        raise ValueError("Physical chart factor population incomplete")
    references = []

    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "file_ids":
                    if len(child) != len(set(child)) or not set(child) <= ids:
                        raise ValueError(
                            "Unresolved/duplicated physical source ID at " + path
                        )
                    references.append(path)
                else:
                    walk(child, path + "." + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, path + f"[{i}]")

    walk(profile, "chart_profile")
    for factor in factors:
        context = source["by_factor"][factor]
        if context["model"] != expected_model or not context["file_ids"]:
            raise ValueError("Chart factor source unknown: " + factor)
    return {
        "physical_factors": len(factors),
        "file_count": len(ids),
        "resolved_contexts": len(references),
        "actual_model": expected_model,
        "accuracy_certified": False,
    }
