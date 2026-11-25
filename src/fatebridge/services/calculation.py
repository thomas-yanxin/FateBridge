"""Integrated destiny analysis using shared birth computation."""

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import calculation_guard


@calculation_guard("命理分析计算")
def calculate_destiny_analysis(person: PersonInfo) -> ServiceResult:
    return build_destiny_payload(build_birth_computation_context(person))
