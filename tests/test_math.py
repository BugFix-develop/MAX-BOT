import unittest
from core.validator import check_answer , normalize_answer

class TestValidator(unittest.TestCase):
    def test_remove_spce_and_case(self):
        self.assertEqual(normalize_answer(" X^2 + 4X + 4"), "x^2+4x+4")

    def test_normalize_cyrillic(self):
        #Проверка замены русской буквы 'х' на латинскую 'x'
        self.assertEqual(normalize_answer("х^2 + 4х + 4"), "x^2+4x+4")
    
    def test_normalize_powers(self):
        #Проверка разных форматов степеней (**, во 2, в квадрате, ²)
        self.assertEqual(normalize_answer("x**2 + 4x + 4"), "x^2+4x+4")
    
    def test_check_answer_correct(self):
        #Проверка совпадения правильных ответов
        is_correct, msg = check_answer("х**2 + 4*x + 4", "x^2 + 4x + 4")
        self.assertTrue(is_correct)

    def test_check_answer_incorrect(self):
        #Проверка неверного ответа
        is_correct, msg = check_answer("x^2 + 5x + 4", "x^2 + 4x + 4")
        self.assertFalse(is_correct)

if __name__ == "__main__":
    unittest.main()
