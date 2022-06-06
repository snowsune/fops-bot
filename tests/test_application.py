import pytest
import os.path

from fops_bot.main import FopsBot


@pytest.fixture
def app():
    return FopsBot()


class TestApplication(object):
    def test_nothing(self):
        assert True

    def test_versioning(self, app):
        # App version must be present
        assert len(app.version) > 1
