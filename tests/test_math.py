import unittest
from core.validator import check_answer , normalize_answer

class TestValidator(unittest.TestCase):
    def test_remove_spce_and_case(self):
        self.assertEqual(normalize_answer(" X^2 + 4X + 4"), "x^2+4x+4")

    def test_normalize_cyrillic(self):
        #Проверка замены русской буквы 'х' на латинскую 'x'
        self.assertEqual(normalize_answer("х^2 + 4х + 4"), "x^2+4x+4")
    
    def test_normalize_powers(self):
        #Проверка разных форматов степеней (**, во 2, в квадрате, ², x2)
        self.assertEqual(normalize_answer("x**2 + 4x + 4"), "x^2+4x+4")
        self.assertEqual(normalize_answer("x² + 4x + 4"), "x^2+4x+4")
        self.assertEqual(normalize_answer("x2 + 4x + 4"), "x^2+4x+4")
        self.assertEqual(normalize_answer("4x2 + 12x + 9"), "4x^2+12x+9")
        self.assertEqual(normalize_answer("(x+2)2"), "(x+2)^2")
        # Степени 4 и 5
        self.assertEqual(normalize_answer("x**4 - 16"), "x^4-16")
        self.assertEqual(normalize_answer("x⁴ - 16"), "x^4-16")
        self.assertEqual(normalize_answer("x4 - 16"), "x^4-16")
        self.assertEqual(normalize_answer("a5 + b5"), "a^5+b^5")
        self.assertEqual(normalize_answer("a⁵ + b⁵"), "a^5+b^5")
        self.assertEqual(normalize_answer("a**5 + b**5"), "a^5+b^5")

    def test_check_answer_correct(self):
        #Проверка совпадения правильных ответов
        is_correct, msg = check_answer("х**2 + 4*x + 4", "x^2 + 4x + 4")
        self.assertTrue(is_correct)
        #Проверка красивого формата x² и x2
        self.assertTrue(check_answer("x² + 4x + 4", "x^2 + 4x + 4")[0])
        self.assertTrue(check_answer("x2 + 4x + 4", "x^2 + 4x + 4")[0])
        # Проверка степеней 4 и 5
        self.assertTrue(check_answer("x⁴ - 16", "x^4 - 16")[0])
        self.assertTrue(check_answer("x4 - 16", "x^4 - 16")[0])
        self.assertTrue(check_answer("a⁵ + b⁵", "a^5 + b^5")[0])
        self.assertTrue(check_answer("a5 + b5", "a^5 + b^5")[0])

    def test_check_answer_incorrect(self):
        #Проверка неверного ответа
        is_correct, msg = check_answer("x^2 + 5x + 4", "x^2 + 4x + 4")
        self.assertFalse(is_correct)

if __name__ == "__main__":
    unittest.main()
