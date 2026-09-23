"""
generic_mutate.py

The pattern-based mutators in mutate.py only fire when a specific string
(".items()", "xrange", "unicode(", etc) is present. Most of the 298 mined
GitHub functions don't contain any of those strings -- they're doing
arbitrary real-world things -- so most of them got ZERO mutants, causing
a ~318:50 positive:negative imbalance.

These mutators work by walking the AST instead, so they apply to almost
ANY function regardless of what it does. Each one makes ONE small,
syntactically-valid change and returns the re-serialized source via
ast.unparse (needs Python 3.9+).

These are intentionally more "generic bug" than "migration-specific bug"
(a flipped comparison operator isn't a python2/3 migration mistake per
se) -- treat them as filling out the negative class with plausible code
bugs, complementary to the migration-specific mutators, not a replacement
for them. difficulty="medium" reflects that distinction.
"""

import ast
import random


class _SingleNodeMutator(ast.NodeTransformer):
    """Base: walks the tree, mutates the Nth matching node (by index),
    leaves everything else untouched. Ensures exactly one change per call."""

    def __init__(self, target_index):
        self.target_index = target_index
        self.seen = 0
        self.changed = False

    def _should_mutate(self):
        hit = (self.seen == self.target_index)
        self.seen += 1
        return hit


_CMP_FLIP = {
    ast.Lt: ast.GtE, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.GtE: ast.Lt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}


class CompareFlipper(_SingleNodeMutator):
    """Flip one comparison operator, e.g. < becomes >=."""
    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            if type(op) in _CMP_FLIP and self._should_mutate():
                node.ops[i] = _CMP_FLIP[type(op)]()
                self.changed = True
                return node
        return node


class BoolOpFlipper(_SingleNodeMutator):
    """Flip 'and' to 'or' or vice versa."""
    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self._should_mutate():
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            self.changed = True
        return node


class OffByOneMutator(_SingleNodeMutator):
    """Increment or decrement one integer literal by 1."""
    def visit_Constant(self, node):
        if isinstance(node.value, int) and not isinstance(node.value, bool):
            if self._should_mutate():
                new_val = node.value + random.choice([-1, 1])
                self.changed = True
                return ast.copy_location(ast.Constant(value=new_val), node)
        return node


class ReturnNoneMutator(_SingleNodeMutator):
    """Replace one 'return <expr>' with 'return None', dropping the value."""
    def visit_Return(self, node):
        if node.value is not None and not (
            isinstance(node.value, ast.Constant) and node.value.value is None
        ):
            if self._should_mutate():
                self.changed = True
                return ast.copy_location(
                    ast.Return(value=ast.Constant(value=None)), node)
        return node


class NegateConditionMutator(_SingleNodeMutator):
    """Wrap one if-condition in 'not (...)', inverting the branch taken."""
    def visit_If(self, node):
        self.generic_visit(node)
        if self._should_mutate():
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            self.changed = True
        return node


MUTATOR_CLASSES = [
    ("generic_comparison_flip", CompareFlipper),
    ("generic_boolop_flip", BoolOpFlipper),
    ("generic_off_by_one", OffByOneMutator),
    ("generic_return_value_dropped", ReturnNoneMutator),
    ("generic_condition_negated", NegateConditionMutator),
]


def _count_matches(tree, mutator_cls):
    """Run once with an impossible target to count how many mutation
    points exist, without actually mutating."""
    counter = mutator_cls(target_index=-1)
    counter.visit(tree)
    return counter.seen


def generate_generic_mutants(code, max_per_type=1, seed=None):
    """
    Given ANY python3 function source, return a list of
    {mutation_type, mutated_code, difficulty} dicts using AST mutation.

    max_per_type: how many mutants to attempt per mutator class (each at
    a different random mutation point) -- keep at 1-2 to avoid exploding
    dataset size from a handful of functions.
    """
    rng = random.Random(seed)
    mutants = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return mutants  # can't mutate unparseable code

    for mutation_type, cls in MUTATOR_CLASSES:
        try:
            n_points = _count_matches(ast.parse(code), cls)
        except Exception:
            continue
        if n_points == 0:
            continue

        n_attempts = min(max_per_type, n_points)
        chosen_indices = rng.sample(range(n_points), n_attempts)

        for idx in chosen_indices:
            try:
                fresh_tree = ast.parse(code)
                mutator = cls(target_index=idx)
                new_tree = mutator.visit(fresh_tree)
                if not mutator.changed:
                    continue
                ast.fix_missing_locations(new_tree)
                mutated_code = ast.unparse(new_tree)
                if mutated_code.strip() == code.strip():
                    continue
                mutants.append(dict(
                    mutation_type=mutation_type,
                    mutated_code=mutated_code,
                    difficulty="medium",
                ))
            except Exception:
                continue  # skip anything that fails to unparse cleanly

    return mutants


if __name__ == "__main__":
    sample = '''
def check(x, y):
    if x < y:
        return x + 1
    return None
'''.strip()
    for m in generate_generic_mutants(sample, max_per_type=2, seed=1):
        print(f"--- {m['mutation_type']} ---")
        print(m["mutated_code"])
        print()
