"""Check source-ID resolution and file-byte integrity without an engine import."""


def verify(result, expected_model, allowed_hashes):
    profile = result["chart"]["params"]["chart_profile"]
    if profile["ephemeris_model"] != expected_model:
        raise ValueError("Actual backend differs")
    else:
        pass
    source = profile.get("physical_ephemeris_source")
    if not isinstance(source, dict):
        raise ValueError("Physical source receipt missing")
    else:
        pass
    if source["has_unidentified_sources"] or source["accuracy_certified"] is not False:
        raise ValueError("Source identity unknown or promoted to accuracy")
    else:
        pass
    files = source["files"]
    ids = {f["id"] for f in files}
    if not ids or len(ids) != len(files):
        raise ValueError("Physical source files absent/duplicated")
    else:
        pass
    for file in files:
        if file["sha256"] not in allowed_hashes:
            raise ValueError("Physical file differs from frozen data")
        else:
            pass
        prefix = "jpl" if expected_model == "jpl" else "se1"
        if file["id"] != f"{prefix}:{file['slot']}:{file['filename']}":
            raise ValueError("File identifier does not bind declared filename/slot")
        else:
            pass
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
    else:
        pass
    references = []

    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "file_ids":
                    if len(child) != len(set(child)) or not set(child) <= ids:
                        raise ValueError(
                            "Unresolved/duplicated physical source ID at " + path
                        )
                    else:
                        pass
                    references.append(path)
                else:
                    walk(child, path + "." + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, path + f"[{i}]")
        else:
            pass

    walk(profile, "chart_profile")
    for factor in factors:
        context = source["by_factor"][factor]
        if context["model"] != expected_model or not context["file_ids"]:
            raise ValueError("Chart factor source unknown: " + factor)
        else:
            pass
    return {
        "physical_factors": len(factors),
        "file_count": len(ids),
        "resolved_contexts": len(references),
        "actual_model": expected_model,
        "accuracy_certified": False,
    }
