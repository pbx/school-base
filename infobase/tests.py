from django.test import TestCase, client

class SmokeTest(TestCase):
    """I.e., does it run?"""
    
    def SetUp(self):
        self.client = client.Client()
        
    def fetch(self, path, status):
        """See if the specified page produces the expected HTTP status"""
        response = self.client.get(path)
        self.failUnlessEqual(response.status_code, status)
        
    def test_pages(self):
        self.fetch("/", 404)
        self.fetch("/scan/", 200)
        self.fetch("/attendance/", 302)

## TODO: to use this test, create a fixture with the account credentials
    # def test_access(self):
    #     response = self.client.login(path="/attendance/", username="instructor", password="instructor")
    #     self.failUnlessEqual(response.status_code, 200)