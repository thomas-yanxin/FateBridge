"""Distinct stellar ranges in Lilly's 1647 planet table and worked example.

P179 prints 'six' (long s) for Regulus and 'five' for Spica. P115 explicitly
prints five for Algol. The closed longitude interval remains the declared
implementation convention, not a 3D conjunction or a physical error bound.
"""

STELLAR_ORB_DEGREES = {"Regulus": 6, "Spica": 5, "Algol": 5}
STELLAR_ORB_SOURCE_PAGES = {"Regulus": [115, 179], "Spica": [115, 179], "Algol": [115]}
