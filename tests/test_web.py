from unittest.mock import MagicMock

import pytest
from oai_repo.response import OAIResponse

from oaipmh.dataprovider import FedoraDataProvider, AvalonDataProvider
from oaipmh.solr import Index
from oaipmh.web import create_app, get_config, status

DEFAULT_SOLR_CONFIG = {
    'base_query': 'item__handle__id:*',
    'handle_field': 'item__handle__id',
    'uri_field': 'id',
    'last_modified_field': 'item__last_modified__dt',
    'auto_create_sets': False,
    'sets': [],
}


@pytest.fixture
def data_provider(monkeypatch, mock_solr_client, mock_solr_result):
    monkeypatch.setenv('ADMIN_EMAIL', 'peichman@umd.edu')
    monkeypatch.setenv('BASE_URL', 'http://localhost:5000/oai/api')
    monkeypatch.setenv('OAI_NAMESPACE_IDENTIFIER', 'fcrepo-local')
    monkeypatch.setenv('OAI_REPOSITORY_NAME', 'UMD Libraries')
    monkeypatch.setenv('DATESTAMP_GRANULARITY', 'YYYY-MM-DD')
    monkeypatch.setenv('EARLIEST_DATESTAMP', '2014-01-01')
    mock_solr_client.search = MagicMock(return_value=mock_solr_result)
    return FedoraDataProvider(
        Index(
            config=DEFAULT_SOLR_CONFIG,
            solr_client=mock_solr_client,
        )
    )


@pytest.fixture
def sample_config(datadir):
    return {
        'base_query': 'hdl:*',
        'handle_field': 'hdl',
        'uri_field': 'id',
        'last_modified_field': 'last_modified',
        'auto_create_sets': False,
        'sets': [],
    }


def test_status_ok():
    oai_response = MagicMock(spec=OAIResponse)
    oai_response.__bool__.return_value = True
    assert status(oai_response) == 200


def test_status_not_found():
    mock_error = MagicMock()
    mock_error.get.return_value = 'noRecordsMatch'
    oai_response = MagicMock(spec=OAIResponse)
    oai_response.__bool__.return_value = False
    oai_response.xpath.return_value = [mock_error]
    assert status(oai_response) == 404


def test_status_bad_request():
    mock_error = MagicMock()
    mock_error.get.return_value = 'otherError'
    oai_response = MagicMock(spec=OAIResponse)
    oai_response.__bool__.return_value = False
    oai_response.xpath.return_value = [mock_error]
    assert status(oai_response) == 400


def test_get_config_default():
    with pytest.raises(RuntimeError):
        get_config(None)


def test_get_config_from_filename(datadir, sample_config):
    assert get_config(str(datadir / 'config.yml')) == sample_config


def test_get_config_from_file(datadir, sample_config):
    with (datadir / 'config.yml').open() as fh:
        assert get_config(fh) == sample_config


def test_root(data_provider):
    app = create_app(data_provider)
    app_client = app.test_client()
    response = app_client.get('/')
    assert response.status_code == 302


def test_home(data_provider):
    app = create_app(data_provider)
    app_client = app.test_client()
    response = app_client.get('/oai')
    assert response.status_code == 200


@pytest.mark.parametrize(
    ('verb', 'parameters'),
    [
        ['Identify', {}],
        ['ListSets', {}],
        ['ListMetadataFormats', {}],
        ['ListIdentifiers', {'metadataPrefix': 'oai_dc'}],
    ]
)
def test_oai_get(data_provider, verb, parameters):
    app = create_app(data_provider=data_provider)
    app_client = app.test_client()
    response = app_client.get('/oai/api', query_string={'verb': verb, **parameters})
    assert response.status_code == 200


@pytest.mark.parametrize(
    ('verb', 'parameters'),
    [
        ['Identify', {}],
        ['ListSets', {}],
        ['ListMetadataFormats', {}],
        ['ListIdentifiers', {'metadataPrefix': 'oai_dc'}],
    ]
)
def test_oai_post(data_provider, verb, parameters):
    app = create_app(data_provider=data_provider)
    app_client = app.test_client()
    response = app_client.post('/oai/api', data={'verb': verb, **parameters})
    assert response.status_code == 200
