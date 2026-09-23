"""
base_pairs.py

Curated, hand-verified Python 2 -> Python 3 migration pairs.
Each entry is a TRUE POSITIVE (equivalent=yes) that also serves as the
seed for mutation-based negatives.

Fields:
    id            : stable short id, used as the "family" key for splitting
    pattern       : which migration pattern this demonstrates (for stratification)
    original_code : python2 snippet
    migrated_code : correct python3 snippet
    repo          : provenance tag (synthetic_curated for this batch)
"""

BASE_PAIRS = [
    dict(
        id="dict_iteritems_01",
        pattern="dict_iteritems",
        original_code='''
def count_items(d):
    result = []
    for k, v in d.iteritems():
        result.append((k, v))
    return result
'''.strip(),
        migrated_code='''
def count_items(d):
    result = []
    for k, v in d.items():
        result.append((k, v))
    return result
'''.strip(),
    ),
    dict(
        id="dict_iterkeys_01",
        pattern="dict_iterkeys",
        original_code='''
def all_keys(d):
    out = []
    for k in d.iterkeys():
        out.append(k)
    return out
'''.strip(),
        migrated_code='''
def all_keys(d):
    out = []
    for k in d.keys():
        out.append(k)
    return out
'''.strip(),
    ),
    dict(
        id="print_statement_01",
        pattern="print_statement",
        original_code='''
def greet(name):
    print "Hello,", name
'''.strip(),
        migrated_code='''
def greet(name):
    print("Hello,", name)
'''.strip(),
    ),
    dict(
        id="except_as_01",
        pattern="except_as",
        original_code='''
def safe_div(a, b):
    try:
        return a / b
    except ZeroDivisionError, e:
        return None
'''.strip(),
        migrated_code='''
def safe_div(a, b):
    try:
        return a / b
    except ZeroDivisionError as e:
        return None
'''.strip(),
    ),
    dict(
        id="division_01",
        pattern="division_operator",
        original_code='''
def half(n):
    return n / 2
'''.strip(),
        migrated_code='''
def half(n):
    return n // 2
'''.strip(),
    ),
    dict(
        id="xrange_01",
        pattern="xrange_range",
        original_code='''
def sum_range(n):
    total = 0
    for i in xrange(n):
        total += i
    return total
'''.strip(),
        migrated_code='''
def sum_range(n):
    total = 0
    for i in range(n):
        total += i
    return total
'''.strip(),
    ),
    dict(
        id="unicode_str_01",
        pattern="unicode_str",
        original_code='''
def to_text(b):
    return unicode(b, "utf-8")
'''.strip(),
        migrated_code='''
def to_text(b):
    return b.decode("utf-8")
'''.strip(),
    ),
    dict(
        id="map_list_01",
        pattern="map_returns_iterator",
        original_code='''
def doubled(nums):
    result = map(lambda x: x * 2, nums)
    return result[0]
'''.strip(),
        migrated_code='''
def doubled(nums):
    result = list(map(lambda x: x * 2, nums))
    return result[0]
'''.strip(),
    ),
    dict(
        id="has_key_01",
        pattern="dict_has_key",
        original_code='''
def contains(d, key):
    return d.has_key(key)
'''.strip(),
        migrated_code='''
def contains(d, key):
    return key in d
'''.strip(),
    ),
    dict(
        id="next_method_01",
        pattern="iterator_next",
        original_code='''
def first(it):
    gen = iter(it)
    return gen.next()
'''.strip(),
        migrated_code='''
def first(it):
    gen = iter(it)
    return next(gen)
'''.strip(),
    ),
    dict(
        id="raise_syntax_01",
        pattern="raise_from",
        original_code='''
def load(x):
    if x is None:
        raise ValueError, "x cannot be None"
    return x
'''.strip(),
        migrated_code='''
def load(x):
    if x is None:
        raise ValueError("x cannot be None")
    return x
'''.strip(),
    ),
    dict(
        id="sorted_cmp_01",
        pattern="sorted_cmp_to_key",
        original_code='''
def sort_desc(items):
    return sorted(items, cmp=lambda a, b: b - a)
'''.strip(),
        migrated_code='''
from functools import cmp_to_key

def sort_desc(items):
    return sorted(items, key=cmp_to_key(lambda a, b: b - a))
'''.strip(),
    ),
    dict(
        id="basestring_01",
        pattern="basestring_str",
        original_code='''
def is_text(x):
    return isinstance(x, basestring)
'''.strip(),
        migrated_code='''
def is_text(x):
    return isinstance(x, str)
'''.strip(),
    ),
    dict(
        id="long_int_01",
        pattern="long_removed",
        original_code='''
def make_big(n):
    return long(n)
'''.strip(),
        migrated_code='''
def make_big(n):
    return int(n)
'''.strip(),
    ),
    dict(
        id="urllib_import_01",
        pattern="stdlib_reorg_urllib",
        original_code='''
import urllib2

def fetch(url):
    return urllib2.urlopen(url).read()
'''.strip(),
        migrated_code='''
import urllib.request

def fetch(url):
    return urllib.request.urlopen(url).read()
'''.strip(),
    ),
    dict(
        id="stringio_01",
        pattern="stdlib_reorg_stringio",
        original_code='''
import StringIO

def buf(text):
    s = StringIO.StringIO()
    s.write(text)
    return s.getvalue()
'''.strip(),
        migrated_code='''
import io

def buf(text):
    s = io.StringIO()
    s.write(text)
    return s.getvalue()
'''.strip(),
    ),
    dict(
        id="dict_values_list_01",
        pattern="dict_values_view",
        original_code='''
def second_value(d):
    vals = d.values()
    return vals[1]
'''.strip(),
        migrated_code='''
def second_value(d):
    vals = list(d.values())
    return vals[1]
'''.strip(),
    ),
    dict(
        id="input_raw_input_01",
        pattern="raw_input_input",
        original_code='''
def ask_name():
    name = raw_input("Name: ")
    return name
'''.strip(),
        migrated_code='''
def ask_name():
    name = input("Name: ")
    return name
'''.strip(),
    ),
    dict(
        id="exec_statement_01",
        pattern="exec_statement",
        original_code='''
def run(code, env):
    exec code in env
'''.strip(),
        migrated_code='''
def run(code, env):
    exec(code, env)
'''.strip(),
    ),
    dict(
        id="zip_list_01",
        pattern="zip_returns_iterator",
        original_code='''
def pair_up(a, b):
    pairs = zip(a, b)
    return len(pairs)
'''.strip(),
        migrated_code='''
def pair_up(a, b):
    pairs = list(zip(a, b))
    return len(pairs)
'''.strip(),
    ),
]

if __name__ == "__main__":
    print(f"Loaded {len(BASE_PAIRS)} base pairs")
    patterns = sorted(set(p["pattern"] for p in BASE_PAIRS))
    print(f"Patterns ({len(patterns)}): {patterns}")
