import unittest
import sys
import os

# Добавляем родительскую директорию в путь для абсолютных импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from game_cli import show_menu

class TestCLI(unittest.TestCase):
    def test_show_menu(self):
        # Тест-заглушка
        self.assertTrue(True)
