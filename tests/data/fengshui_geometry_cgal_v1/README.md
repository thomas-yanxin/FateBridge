# Fixed spatial geometry reference

Generated outside the production package using unmodified CGAL6.2.1, an exact rational Cartesian kernel, mpmath1.3.0 at90decimal digits and DEAP1.4.3's original dominance/nondominated-sort APIs. No FateBridge import or output supplied the answers. Original inputs and criteria preceded the runtime edits; references and original failures remain in the external fatebridge-spatial-independent-20261112 audit artifact.

The rational backend changed from the initially planned Gmpq to CGAL-supported Boost cpp_rational because local MPFR headers were unavailable; exact numeric gates did not change. The signed CGAL release archive SHA and actual driver/answer SHA are in metadata. Production does not depend on CGAL or DEAP.

Includes2965angular differences,2107closed direction cases,3010primitive-frame cases,301angle/shape groups,10448qualified visibility cases plus2invalid-observer controls,1484exact cone-shadow areas,27decimal-grid cases,11664known-objective dominance pairs and64nondominated sets. Unknown dimensions are a separately named incomparable project policy. Counts overlap; they are not independent algorithms or prediction trials.

The visibility reference uses a surrounding convex bound and declared opaque footprints, not inferred opaque room walls. Its cardinal-facing45/90degree field-of-view rays are rational. It requires a positive angular-width visible target interval. Shadow references use CGAL's actual3Dconvex hull, then exact cone-plane clipping, not the production edge enumeration or a ray-sampled area estimate. Output areas use the original2e-12*max(1,display_area) square-metre gate. Coordinates use2e-12metres; sine/cosine2e-15; exact angle and direction decisions retain half-open/closed conventions.

This is finite-model validation, not physical site measurements, all continuous inputs, universal Feng Shui rules or real-world efficacy. Higher-level scene, backing/corner and author-condition source adjudication remain separate. The small bundle is maintained for self-contained CI; full source archives and reproducibility logs stay outside the repository.
