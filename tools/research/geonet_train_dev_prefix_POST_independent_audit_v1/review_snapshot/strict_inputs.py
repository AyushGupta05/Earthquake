"""Pure strict input primitives; public collector schema binding remains pending.

No filesystem, network, transport, acquisition, or actual-input interface.
"""
import hashlib
import json
import math
import re

SHA = re.compile(r'[0-9a-f]{64}\Z')


class Invalid(ValueError):
    """Fixed public diagnostic label, never raw private input text."""


def need(condition, label):
    if not condition:
        raise Invalid(label)


def fields(value, expected, label):
    # Native JSON keys are strings. Reject foreign key/comparison objects before
    # any hashing or equality against the declared schema.
    need(type(value) is dict and all(type(key) is str for key in value), label)
    need(set(value) == set(expected), label)


def integer(value, label, minimum=0, maximum=None):
    need(type(value) is int and value >= minimum and
         (maximum is None or value <= maximum), label)
    return value


def number(value, label):
    need(type(value) in (int, float), label)
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError):
        finite = False
    need(finite, label)
    return value


def boolean(value, label):
    need(type(value) is bool, label)
    return value


def text(value, expected, label):
    need(type(value) is str and value == expected, label)
    return value


def sha(value, label):
    need(type(value) is str and SHA.fullmatch(value) is not None, label)
    return value


def digest(raw):
    need(type(raw) is bytes, 'hash_input_type')
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise Invalid('json_duplicate_key')
        value[key] = item
    return value


def decode(raw, byte_cap, label, *, depth_cap=32, node_cap=16384):
    need(type(raw) is bytes and 0 < len(raw) <= byte_cap, label + '_bytes')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(Invalid('json_nonfinite')))
    except Invalid:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise Invalid(label + '_json') from None
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        need(depth <= depth_cap and nodes <= node_cap, label + '_structure_bound')
        if type(item) is float:
            need(math.isfinite(item), 'json_nonfinite')
        elif type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    return value


def same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        if not all(type(key) is str for key in left) or not all(type(key) is str for key in right):
            return False
        return left.keys() == right.keys() and all(same(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(same(x, y) for x, y in zip(left, right))
    if type(left) not in (str, int, float, bool, type(None)):
        return False
    return left == right
