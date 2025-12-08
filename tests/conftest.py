from datetime import datetime
from unittest.mock import MagicMock

import pysolr
import pytest


collect_ignore = ["test_harvester.py"]


class MockSolrResult:
    @property
    def hits(self):
        return len(list(self))

    @property
    def docs(self):
        return list(self)

    def __iter__(self):
        return iter([
            {'item__handle__id': '1903.1/sample1', 'item__last_modified__dt': str(datetime.now())},
            {'item__handle__id': '1903.1/sample2', 'item__last_modified__dt': str(datetime.now())},
            {'item__handle__id': '1903.1/sample3', 'item__last_modified__dt': str(datetime.now())},
        ])


@pytest.fixture
def mock_solr_client():
    mock_solr = MagicMock(spec=pysolr.Solr)
    mock_solr.url = 'http://localhost:8985/solr/fcrepo'
    return mock_solr


@pytest.fixture
def mock_solr_result():
    return MockSolrResult()
