"""
mutate.py

Given a *correct* python3 migrated snippet, produce one or more
"plausible but wrong" mutants -- i.e. hard negatives for the DL verifier.

Each mutator targets ONE realistic migration mistake, tagged with a
mutation_type, so downstream you know *why* a negative is a negative
(this also directly feeds the "Risk Explanation" module later).

IMPORTANT: this script does NOT claim the mutants are behaviorally
different with certainty -- it only re-introduces a *known-risky*
pattern. Confirm with the lightweight verification harness (see
verify_mutants.py) before trusting the label as "strong".
"""

import re
import copy

# ---------------------------------------------------------------------------
# Each mutator: (mutation_type, fn(migrated_code, pattern) -> mutated_code | None)
# Returns None if the mutator doesn't apply to this snippet.
# ---------------------------------------------------------------------------

def mut_reintroduce_iteritems(code, pattern):
    if ".items()" not in code:
        return None
    # Subtle bug: convert .items() to list(...items()) is fine, but here we
    # simulate a *wrong* fix: leave it calling .iteritems() (removed in py3)
    return code.replace(".items()", ".iteritems()")


def mut_flip_division(code, pattern):
    if "//" not in code:
        return None
    return code.replace("//", "/", 1)


def mut_wrong_division_direction(code, pattern):
    # For snippets that correctly use "/", flip to "//" (wrong if float
    # division was intended). Skip if the snippet already uses "//"
    # anywhere -- that case is handled by mut_flip_division instead, and
    # touching both operators in one snippet gets ambiguous.
    if "//" in code:
        return None
    if " / " in code:
        return code.replace(" / ", " // ", 1)
    return None


def mut_drop_list_wrap(code, pattern):
    # Any snippet that wraps an iterator-producing call (map/zip/.values()/
    # .keys()/.items()) in list(...) -- dropping the wrap is a classic
    # migration bug when code downstream expects indexing/len()/multiple
    # iteration. Content-based: fires whenever list( wraps one of these.
    if not re.search(r"list\((map|zip|\w+\.(values|keys|items))\(", code):
        return None
    return _strip_first_list_wrap(code)


def _strip_first_list_wrap(code):
    # naive but effective for our controlled snippets: remove the first
    # "list(" and its matching closing paren
    idx = code.find("list(")
    if idx == -1:
        return None
    start = idx + len("list(")
    depth = 1
    i = start
    while i < len(code) and depth > 0:
        if code[i] == "(":
            depth += 1
        elif code[i] == ")":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    inner = code[start:i - 1]
    return code[:idx] + inner + code[i:]


def mut_reintroduce_iterkeys(code, pattern):
    if ".keys()" not in code:
        return None
    return code.replace(".keys()", ".iterkeys()")


def mut_wrong_except_var_scope(code, pattern):
    if "except ZeroDivisionError as e:\n        return None" not in code:
        return None
    # Bug: instead of returning None on the error path, the migrator
    # accidentally returns the exception object itself -- a realistic
    # mistake when refactoring 'except X, e' -> 'except X as e' by hand,
    # and a reachable behavioral change (return type differs on error).
    return code.replace(
        "except ZeroDivisionError as e:\n        return None",
        "except ZeroDivisionError as e:\n        return e",
    )


def mut_unicode_decode_wrong_encoding(code, pattern):
    if 'decode("utf-8")' not in code:
        return None
    return code.replace('decode("utf-8")', 'decode("ascii")')


def mut_has_key_incomplete(code, pattern):
    if " in d" not in code:
        return None
    # Bug: migrated to 'in d.keys()' works but combined with a stale
    # has_key-style negation mistake -- here simulate dropped membership check
    return code.replace("return key in d", "return d")


def mut_next_wrong_target(code, pattern):
    if "next(gen)" not in code:
        return None
    # Bug: calls next() on the iterable itself instead of the iterator
    return code.replace("next(gen)", "next(it)")


def mut_cmp_to_key_dropped_import(code, pattern):
    if "from functools import cmp_to_key" not in code:
        return None
    return code.replace("from functools import cmp_to_key\n\n", "")


def mut_stdlib_partial_rename(code, pattern):
    if "urllib.request" not in code:
        return None
    # Bug: import updated but call site still uses old py2 module path
    return code.replace("urllib.request.urlopen", "urllib2.urlopen")


def mut_stringio_wrong_module(code, pattern):
    if "io.StringIO" not in code:
        return None
    return code.replace("io.StringIO", "io.BytesIO")


def mut_long_to_float(code, pattern):
    if "return int(n)" not in code:
        return None
    # Bug: silently changes numeric semantics
    return code.replace("return int(n)", "return float(n)")


def mut_exec_arg_order(code, pattern):
    if "exec(code, env)" not in code:
        return None
    return code.replace("exec(code, env)", "exec(env, code)")


def mut_print_dropped_arg(code, pattern):
    if 'print("Hello,", name)' not in code:
        return None
    return code.replace('print("Hello,", name)', 'print("Hello,")')


def mut_raise_wrong_type(code, pattern):
    if 'raise ValueError("x cannot be None")' not in code:
        return None
    return code.replace(
        'raise ValueError("x cannot be None")',
        'raise TypeError("x cannot be None")',
    )


def mut_xrange_off_by_one(code, pattern):
    if "range(n)" not in code:
        return None
    return code.replace("range(n)", "range(n - 1)")


def mut_basestring_wrong_type(code, pattern):
    if "isinstance(x, str)" not in code:
        return None
    # Bug: migrator picks bytes instead of str -- plausible confusion when
    # porting basestring, and behaviorally wrong for normal text input.
    return code.replace("isinstance(x, str)", "isinstance(x, bytes)")


def mut_input_no_prompt(code, pattern):
    if 'input("Name: ")' not in code:
        return None
    return code.replace('input("Name: ")', "input()")


def mut_has_key_wrong_negation(code, pattern):
    return None  # reserved / placeholder for future expansion


MUTATORS = [
    ("dict_iteritems_not_converted", mut_reintroduce_iteritems),
    ("dict_iterkeys_not_converted", mut_reintroduce_iterkeys),
    ("basestring_narrowed_to_bytes", mut_basestring_wrong_type),
    ("division_operator_flipped", mut_flip_division),
    ("division_operator_wrong_direction", mut_wrong_division_direction),
    ("missing_list_wrap_on_iterator", mut_drop_list_wrap),
    ("except_var_used_outside_scope", mut_wrong_except_var_scope),
    ("wrong_decode_encoding", mut_unicode_decode_wrong_encoding),
    ("has_key_membership_check_dropped", mut_has_key_incomplete),
    ("next_called_on_wrong_target", mut_next_wrong_target),
    ("cmp_to_key_import_dropped", mut_cmp_to_key_dropped_import),
    ("stdlib_rename_partial", mut_stdlib_partial_rename),
    ("stringio_wrong_module", mut_stringio_wrong_module),
    ("long_to_int_became_float", mut_long_to_float),
    ("exec_argument_order_swapped", mut_exec_arg_order),
    ("print_argument_dropped", mut_print_dropped_arg),
    ("raise_wrong_exception_type", mut_raise_wrong_type),
    ("range_off_by_one", mut_xrange_off_by_one),
    ("input_prompt_dropped", mut_input_no_prompt),
]


def generate_mutants(base_pair):
    """
    Given one BASE_PAIRS entry, return a list of mutant dicts:
        { mutation_type, mutated_code, difficulty }
    Only mutators that actually apply (and actually change the code) fire.
    """
    mutants = []
    for mutation_type, fn in MUTATORS:
        try:
            result = fn(base_pair["migrated_code"], base_pair["pattern"])
        except Exception:
            result = None
        if result and result.strip() != base_pair["migrated_code"].strip():
            mutants.append(dict(
                mutation_type=mutation_type,
                mutated_code=result,
                difficulty="hard",  # mutation-based negatives = hard by default
            ))
    return mutants


if __name__ == "__main__":
    from base_pairs import BASE_PAIRS
    total = 0
    for bp in BASE_PAIRS:
        ms = generate_mutants(bp)
        total += len(ms)
        print(f"{bp['id']:30s} -> {len(ms)} mutant(s): {[m['mutation_type'] for m in ms]}")
    print(f"\nTotal mutants generated: {total}")
