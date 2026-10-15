"""Aggregate and filter all rules based on detected project stacks."""
from typing import List, Set
from .base import Rule
from .common import COMMON_RULES
from .laravel import LARAVEL_RULES
from .node import NODE_RULES
from .nextjs import NEXTJS_RULES
from .python import PYTHON_RULES
from .flutter import FLUTTER_RULES
from .database import DATABASE_RULES
from .design import GodFileRule


def get_applicable_rules(stacks: Set[str]) -> List[Rule]:
    rules: List[Rule] = list(COMMON_RULES)
    rules.append(GodFileRule())

    # Add stack-specific rules
    stack_rule_maps = [
        (LARAVEL_RULES, {'laravel', 'php'}),
        (NODE_RULES, {'node', 'node_backend'}),
        (NEXTJS_RULES, {'nextjs', 'react'}),
        (PYTHON_RULES, {'python'}),
        (FLUTTER_RULES, {'flutter'}),
        (DATABASE_RULES, {'database', 'docker', 'firebase'})
    ]

    for rule_list, stack_set in stack_rule_maps:
        if bool(stacks & stack_set):
            rules.extend(rule_list)

    return rules
