"""Closed JSON and bounded member reads, with no filesystem authority."""
import hashlib
import json
import math
import re

HEX = re.compile(r'[0-9a-f]{64}\Z')


class Reject(ValueError):
    pass


def integer(value, low=None, high=None):
    if type(value) is not int or (low is not None and value < low) or (high is not None and value > high):
        raise Reject('integer')
    return value


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise Reject('keys')
    return value


def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise Reject('duplicate_key')
        out[key] = value
    return out


def _constant(_):
    raise Reject('json_constant')


def load(raw, cap):
    if type(raw) is not bytes or len(raw) > cap:
        raise Reject('json_cap_or_type')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Reject('json') from exc
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > 32:
            raise Reject('depth')
        if type(item) is float and not math.isfinite(item):
            raise Reject('finite_json')
        if type(item) is list:
            stack.extend((x, depth + 1) for x in item)
        elif type(item) is dict:
            stack.extend((x, depth + 1) for x in item.values())
    return value


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    except (ValueError, TypeError, RecursionError) as exc:
        raise Reject('canonical') from exc


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value, cap):
    keys(value, ('bytes', 'sha256'))
    integer(value['bytes'], 0, cap)
    if type(value['sha256']) is not str or not HEX.fullmatch(value['sha256']):
        raise Reject('pin')
    return value


def member(reader, name, expected, cap):
    pin(expected, cap)
    raw = reader(name, expected['bytes'] + 1)
    if type(raw) is not bytes or len(raw) != expected['bytes'] or sha(raw) != expected['sha256']:
        raise Reject('member')
    return raw
