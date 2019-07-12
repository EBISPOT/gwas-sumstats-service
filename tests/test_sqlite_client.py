import os
import unittest
import config


class TestDB(unittest.TestCase):
    def test_database_exists(self):
        tester = os.path.exists(config.DB_PATH)
        self.assertTrue(tester)


if __name__ == '__main__':
    unittest.main()
