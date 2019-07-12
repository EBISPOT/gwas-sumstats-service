import os
import unittest
from app import app
import config

class BasicTestCase(unittest.TestCase):

    def test_index(self):
        tester = app.test_client()
        response = tester.get('/', content_type='html/json')
        study_link = response.get_json()['_links']['studies']['href']
        self.assertEqual(response.status_code, 200)
        self.assertRegex(study_link, "http://.*studies")

    def test_studies_endpoint(self):
        tester = app.test_client(self)
        response = tester.get('/studies', content_type='html/json')
        self.assertEqual(response.status_code, 200)

    def test_database(self):
        tester = os.path.exists(config.DB_PATH)
        self.assertTrue(tester)


if __name__ == '__main__':
    unittest.main()
