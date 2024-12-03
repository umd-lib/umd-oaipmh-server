from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from lxml import etree
from os import environ
from oai_repo import Set, RecordHeader
from oai_repo.exceptions import OAIErrorCannotDisseminateFormat, OAIRepoExternalException

from oaipmh.dataprovider import DataProvider, FedoraDataProvider, DataProviderType
from oaipmh.oai import OAIIdentifier
from oaipmh.solr import Index

environ['DATA_PROVIDER_TYPE'] = 'fedora'
environ['JWT_SECRET'] = str(uuid4())
DEFAULT_SOLR_CONFIG = {
    'base_query': 'item__handle__id:*',
    'handle_field': 'item__handle__id',
    'uri_field': 'id',
    'last_modified_field': 'item__last_modified__dt',
    'auto_create_sets': False,
    'sets': [],
}


@pytest.fixture
def index_with_defaults(mock_solr_client):
    return Index(
        solr_client=mock_solr_client,
        config=DEFAULT_SOLR_CONFIG,
    )


@pytest.fixture
def index_with_auto_sets(mock_solr_client):
    return Index(
        solr_client=mock_solr_client,
        config={
            'base_query': 'item__handle__id:*',
            'handle_field': 'item__handle__id',
            'uri_field': 'id',
            'last_modified_field': 'item__last_modified__dt',
            'auto_create_sets': True,
            'auto_set': {
                'query': 'resource_type__facet:Collection',
                'name_field': 'item__title__txt',
                'name_query_field': 'admin_set__facet',
            },
            'sets': [],
        })


@pytest.fixture
def provider(mock_solr_client, index_with_auto_sets):
    return FedoraDataProvider(index=index_with_auto_sets)


@pytest.fixture
def xml():
    return etree.XML('<rdf:Description xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>')


@pytest.fixture
def prange_text(datadir):
    return (datadir / 'prange_poster.xml').read_text()


@pytest.fixture
def prange_rdf(datadir):
    return etree.parse(datadir / 'prange_poster.xml')


def test_dataprovider(monkeypatch, provider):
    monkeypatch.setenv('OAI_NAMESPACE_IDENTIFIER', 'fcrepo')
    assert provider.is_valid_identifier('oai:fcrepo:foo')
    assert not provider.is_valid_identifier('oai:other:thing')


def test_transform_unsupported_format(provider, xml):
    with pytest.raises(OAIErrorCannotDisseminateFormat):
        provider.transform('fake', xml)


@pytest.mark.parametrize(
    ('transformer', 'result_tag'),
    [
        ('oai_dc', '{http://www.openarchives.org/OAI/2.0/oai_dc/}dc'),
        ('rdf', '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF'),
    ]
)
def test_transform(provider, prange_rdf, transformer, result_tag):
    result = provider.transform(transformer, prange_rdf)
    assert result.tag == result_tag


def test_identify(monkeypatch, provider):
    monkeypatch.setenv('ADMIN_EMAIL', 'jdoe@example.com')
    monkeypatch.setenv('BASE_URL', 'http://localhost:5555/')
    monkeypatch.setenv('DATESTAMP_GRANULARITY', 'YYYY-MM-DD')
    monkeypatch.setenv('EARLIEST_DATESTAMP', '2020-01-01')
    monkeypatch.setenv('OAI_REPOSITORY_NAME', 'foo records')
    monkeypatch.setenv('REPORT_DELETED_RECORDS', 'yes')

    identify = provider.get_identify()
    assert identify.admin_email == ['jdoe@example.com']
    assert identify.base_url == 'http://localhost:5555/'
    assert identify.granularity == 'YYYY-MM-DD'
    assert identify.earliest_datestamp == '2020-01-01'
    assert identify.repository_name == 'foo records'
    assert identify.deleted_record == 'yes'


def test_get_metadata_formats(provider):
    formats = provider.get_metadata_formats()
    assert len(formats) == 2
    assert {f.metadata_prefix for f in formats} == {'oai_dc', 'rdf'}


@pytest.mark.parametrize(
    ('local_identifier', 'expected'),
    [
        ('foo', 'oai:fcrepo:foo'),
        ('http://fcrepo-local:8080/fcrepo/rest/bar', 'oai:fcrepo:http%3A//fcrepo-local%3A8080/fcrepo/rest/bar'),
    ]
)
def test_get_oai_identifier(monkeypatch, provider, local_identifier, expected):
    monkeypatch.setenv('OAI_NAMESPACE_IDENTIFIER', 'fcrepo')
    identifier = provider.get_oai_identifier(local_identifier)
    assert isinstance(identifier, OAIIdentifier)
    assert str(identifier) == expected


def test_handle_not_found(provider):
    provider.index.solr.search = MagicMock(return_value=[])
    with pytest.raises(OAIRepoExternalException):
        provider.get_record_header('oai:fcrepo:foo')


def test_get_record_header(mock_solr_client):
    mock_index = Index(config=DEFAULT_SOLR_CONFIG, solr_client=mock_solr_client)
    mock_index.get_doc = MagicMock(
        return_value={
            'id': 'oai:fcrepo:foo',
            'item__last_modified__dt': '2023-06-16T08:37:29Z',
        }
    )
    provider = FedoraDataProvider(index=mock_index)
    header = provider.get_record_header('oai:fcrepo:foo')
    assert isinstance(header, RecordHeader)
    assert header.identifier == 'oai:fcrepo:foo'
    assert header.datestamp == '2023-06-16T08:37:29Z'


def test_list_set_specs(index_with_defaults):
    index_with_defaults.get_sets = MagicMock(return_value={
        'foo': {
            'spec': 'foo',
            'name': 'Foo',
            'filter': 'collection_title_facet:Foo',
        },
        'bar': {
            'spec': 'bar',
            'name': 'Bar',
            'filter': 'collection_title_facet:Bar',
        },
    })
    index_with_defaults.get_sets_for_handle = MagicMock(return_value={
        'bar': {
            'spec': 'bar',
            'name': 'Bar',
            'filter': 'collection_title_facet:Bar',
        },
    })
    provider = FedoraDataProvider(index=index_with_defaults)
    sets, length, _ = provider.list_set_specs()
    assert sets == {'foo', 'bar'}
    assert length == 2

    sets, length, _ = provider.list_set_specs(identifier='oai:fcrepo-test:foo')
    assert sets == {'bar'}
    assert length == 1


def test_get_sets(index_with_defaults):
    index_with_defaults.get_sets = MagicMock(return_value={
        'foo': {
            'spec': 'foo',
            'name': 'Foo',
            'filter': 'collection_title_facet:Foo',
        },
        'bar': {
            'spec': 'bar',
            'name': 'Bar',
            'filter': 'collection_title_facet:Bar',
        },
    })
    provider = FedoraDataProvider(index=index_with_defaults)
    oai_set = provider.get_set('bar')
    assert isinstance(oai_set, Set)
    assert oai_set.spec == 'bar'
    assert oai_set.name == 'Bar'
    assert oai_set.description == []


def test_get_record_abouts(provider):
    # currently, this always returns an empty list
    assert provider.get_record_abouts('oai:fcrepo:foo') == []


class OKResponse:
    ok = True

    def __init__(self, text):
        self.text = text

    def __call__(self, *args, **kwargs):
        return self


def test_get_record_metadata(index_with_auto_sets, prange_text):
    fedora_provider = FedoraDataProvider(index_with_auto_sets)
    fedora_provider.session.get = MagicMock(return_value=OKResponse(prange_text))
    results = MagicMock()
    results.docs = [{'id': 'http://example.com/foo', 'handle': 'foo'}]
    fedora_provider.index.solr.search = MagicMock(return_value=results)

    assert fedora_provider.get_record_metadata('oai:fcrepo:foo', 'oai_dc') is not None
    assert fedora_provider.index.solr.search.call_count == 1


class NotFoundResponse:
    ok = False
    status_code = 404
    reason = 'Not Found'


def test_get_record_metadata_not_found(index_with_auto_sets):
    fedora_provider = FedoraDataProvider(index=index_with_auto_sets)
    fedora_provider.session.get = MagicMock(return_value=NotFoundResponse())
    with pytest.raises(OAIRepoExternalException) as e:
        fedora_provider.get_record_metadata('oai:fcrepo:foo', 'oai_dc')

    assert str(e.value) == 'Unable to retrieve resource from fcrepo'


def test_list_identifiers(monkeypatch, provider, mock_solr_client, mock_solr_result):
    monkeypatch.setenv('OAI_NAMESPACE_IDENTIFIER', 'fcrepo')
    mock_solr_client.search = MagicMock(return_value=mock_solr_result)
    identifiers, hits, _ = provider.list_identifiers(metadataprefix='oai_dc')
    assert hits == 3
    assert identifiers == [
        'oai:fcrepo:1903.1/sample1',
        'oai:fcrepo:1903.1/sample2',
        'oai:fcrepo:1903.1/sample3',
    ]


@pytest.mark.parametrize(
    ('data_provider_type', 'expected_class'),
    [('fedora', FedoraDataProvider)]
)
def test_dataprovider_enum_valid(data_provider_type, expected_class):
    assert DataProviderType[data_provider_type].value is expected_class


@pytest.mark.parametrize(
    ('data_provider_type'),
    ['Fedoraa', 'asdf', 'not_a_valid_provider']
)
def test_dataprovider_enum_invalid(data_provider_type):
    with pytest.raises(KeyError):
        DataProviderType[data_provider_type]
