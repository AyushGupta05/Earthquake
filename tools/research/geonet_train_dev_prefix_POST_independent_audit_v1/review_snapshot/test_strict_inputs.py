"""Invented-only primitive tests; no actual plan, reader, transport, or vendor code."""
import unittest

import strict_inputs as s


class Hostile:
    def __eq__(self, other):
        raise AssertionError('foreign comparison was executed')

    def __hash__(self):
        return 1


class StringSubclass(str):
    def __eq__(self, other):
        raise AssertionError('foreign string comparison was executed')

    __hash__ = str.__hash__


class IntSubclass(int):
    def __eq__(self, other):
        raise AssertionError('foreign integer comparison was executed')


class PrimitiveTests(unittest.TestCase):
    def test_wrong_scalar_types_rejected_without_hostile_comparison(self):
        for value in (Hostile(), StringSubclass('expected'), IntSubclass(1), True, None, []):
            for call in (lambda: s.text(value, 'expected', 'type'),
                         lambda: s.integer(value, 'type'),
                         lambda: s.sha(value, 'type')):
                with self.assertRaises(s.Invalid):
                    call()
        for value in (Hostile(), IntSubclass(1), StringSubclass('1'), True):
            with self.assertRaises(s.Invalid):
                s.number(value, 'type')

    def test_exact_dictionary_schema_rejects_foreign_keys_and_subclasses(self):
        for value in ({Hostile(): 1}, {StringSubclass('a'): 1}, [], None, {'a': 1, 'b': 2}):
            with self.assertRaises(s.Invalid):
                s.fields(value, {'a'}, 'schema')
        s.fields({'a': 1}, {'a'}, 'schema')

    def test_json_duplicate_nonfinite_utf8_depth_node_and_byte_bounds(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}',
                    b'{"a":1e999}', b'\xff', b'[' * 34 + b'0' + b']' * 34,
                    b'', b' ' * 1025):
            with self.assertRaises(s.Invalid):
                s.decode(raw, 1024, 'input')
        with self.assertRaises(s.Invalid):
            s.decode(b'[0,1,2,3,4]', 1024, 'input', node_cap=5)
        for raw in (bytearray(b'{}'), '{}', StringSubclass('{}')):
            with self.assertRaises(s.Invalid):
                s.decode(raw, 1024, 'input')

    def test_huge_numeric_overflow_boolean_alias_and_finite_scalar_boundaries(self):
        for value in (10 ** 10000, float('nan'), float('inf'), True):
            with self.assertRaises(s.Invalid):
                s.number(value, 'clock')
        self.assertEqual(s.number(0, 'clock'), 0)
        self.assertEqual(s.number(0.5, 'clock'), 0.5)
        self.assertEqual(s.integer(0, 'count', maximum=1), 0)
        for value in (-1, 2, 1.0, True):
            with self.assertRaises(s.Invalid):
                s.integer(value, 'count', maximum=1)

    def test_decoded_agreement_preserves_nested_json_types(self):
        self.assertFalse(s.same({'n': 1}, {'n': True}))
        self.assertFalse(s.same({'n': 1}, {'n': 1.0}))
        self.assertFalse(s.same([1], [True]))
        self.assertTrue(s.same(s.decode(b'{"b":[1,2],"a":true}', 1024, 'input'),
                               s.decode(b'{ "a":true, "b":[1,2] }', 1024, 'input')))
        for value in (Hostile(), StringSubclass('a'), IntSubclass(1)):
            self.assertFalse(s.same(value, value))
            self.assertFalse(s.same({'a': value}, {'a': value}))


if __name__ == '__main__':
    unittest.main()
