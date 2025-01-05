import unittest

from atmfjstc.lib.binary_utils.bit_ops import get_set_bits, split_powers2, count_bits, is_power_of_2


class GetSetBitsTest(unittest.TestCase):
    def test_rando(self):
        self.assertEqual(get_set_bits(189), [0, 2, 3, 4, 5, 7])

    def test_zero(self):
        self.assertEqual(get_set_bits(0), [])

    def test_more_32_bit(self):
        self.assertEqual(get_set_bits(1 << 32), [32])

    def test_more_64_bit(self):
        self.assertEqual(get_set_bits(1 << 64), [64])

    def test_negative(self):
        with self.assertRaises(ValueError):
            get_set_bits(-1)


class SplitPowers2Test(unittest.TestCase):
    def test_rando(self):
        self.assertEqual(split_powers2(189), [1, 4, 8, 16, 32, 128])

    def test_zero(self):
        self.assertEqual(split_powers2(0), [])

    def test_more_32_bit(self):
        self.assertEqual(split_powers2(1 << 32), [1 << 32])

    def test_more_64_bit(self):
        self.assertEqual(split_powers2(1 << 64), [1 << 64])

    def test_negative(self):
        with self.assertRaises(ValueError):
            split_powers2(-1)


class CountBitsTest(unittest.TestCase):
    def test_rando(self):
        self.assertEqual(count_bits(189), 6)

    def test_pow2(self):
        self.assertEqual(count_bits(128), 1)

    def test_zero(self):
        self.assertEqual(count_bits(0), 0)

    def test_more_32_bit(self):
        self.assertEqual(count_bits(1 << 32), 1)

    def test_more_64_bit(self):
        self.assertEqual(count_bits(1 << 64), 1)

    def test_negative(self):
        with self.assertRaises(ValueError):
            count_bits(-1)


class IsPowerOf2Test(unittest.TestCase):
    def test_true(self):
        self.assertTrue(is_power_of_2(128))

    def test_false(self):
        self.assertFalse(is_power_of_2(129))

    def test_zero(self):
        self.assertFalse(is_power_of_2(0))

    def test_more_32_bit(self):
        self.assertTrue(is_power_of_2(1 << 32))

    def test_more_64_bit(self):
        self.assertTrue(is_power_of_2(1 << 64))

    def test_negative(self):
        with self.assertRaises(ValueError):
            is_power_of_2(-1)


if __name__ == '__main__':
    unittest.main()
