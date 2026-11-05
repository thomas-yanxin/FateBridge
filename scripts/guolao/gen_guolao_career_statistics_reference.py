"""Regenerate the synthetic component oracle with an independent SciPy install.

Original reference collector: SciPy 1.16.3; generator retained for provenance.
Requires a separately provisioned NumPy/SciPy environment; ordinary test runs read the original numerical reference.
This is not a cohort, event data, forecast generator or runtime dependency.
"""

import hashlib
import json
import math
import platform
import random
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import bootstrap
from scipy.stats._resampling import BootstrapResult

values = np.array([-0.25, 0.125, -0.0625, 0.5, 0.03125])
rng = random.Random(20261022)
# Resample the five declared paired differences, not each model independently.
means = np.array([np.mean(rng.choices(values, k=len(values))) for _ in range(10000)])
prior = BootstrapResult(
    confidence_interval=None,
    bootstrap_distribution=means,
    standard_error=float(np.std(means, ddof=1)),
)
result = bootstrap(
    (values,),
    np.mean,
    method="BCa",
    confidence_level=0.95,
    n_resamples=0,
    bootstrap_result=prior,
    rng=np.random.default_rng(1),
)
ref = {
    "data_kind": "synthetic_component_reference_not_a_study",
    "source": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html",
    "scipy_version": scipy.__version__,
    "numpy_version": np.__version__,
    "python": platform.python_version(),
    "paired_differences": values.tolist(),
    "resamples": 10000,
    "python_choices_seed": 20261022,
    "method": "SciPy public bootstrap BCa using a separately generated fixed bootstrap distribution; n_resamples=0 appends no new draws",
    "interval": [
        float(result.confidence_interval.low),
        float(result.confidence_interval.high),
    ],
    "bootstrap_distribution_sha256_float64_le": hashlib.sha256(
        means.astype("<f8").tobytes()
    ).hexdigest(),
    "calibration_analytic_reference": {
        "description": "Independent closed-form binomial score solution: 9 trials at each p=.2,.5,.8 with 3,6,8 events; unpenalized logit MLE a=log(2),b=1. Observed-information inverse gives Var(a)=13/58 and Var(b)=11/(29*log(4)^2).",
        "intercept": math.log(2),
        "slope": 1.0,
        "intercept_variance": 13 / 58,
        "slope_variance": 11 / (29 * math.log(4) ** 2),
    },
}
(
    Path(__file__).resolve().parents[2]
    / "tests/fixtures/guolao-career-statistics-reference.json"
).write_text(json.dumps(ref, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(ref))
