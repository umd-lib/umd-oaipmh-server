from datetime import datetime
from unittest.mock import MagicMock

import pysolr
import pytest
from oai_repo import OAIRepoExternalException, OAIRepoInternalException

from oaipmh.solr import solr_date_range, Index

DEFAULT_SOLR_CONFIG = {
    'base_query': 'item__handle__id:*',
    'handle_field': 'item__handle__id',
    'uri_field': 'id',
    'last_modified_field': 'item__last_modified__dt',
    'auto_create_sets': False,
    'sets': [],
}


@pytest.mark.parametrize(
    ('timestamp_from', 'timestamp_until'),
    [
        ('not a date', 'also not'),
        (datetime.fromisoformat('2023-06-16'), 'not a date'),
        ('not a date', datetime.fromisoformat('2023-06-16')),
        ('not a date', None),
        (None, 'not a date'),
    ]
)
def test_solr_date_range_invalid(timestamp_from, timestamp_until):
    with pytest.raises(TypeError):
        solr_date_range(timestamp_from, timestamp_until)


@pytest.mark.parametrize(
    ('timestamp_from', 'timestamp_until', 'expected'),
    [
        (None, None, '[* TO *]'),
        (datetime.fromisoformat('2023-06-15'), None, '[2023-06-15T00:00:00Z TO *]'),
        (None, datetime.fromisoformat('2023-06-15'), '[* TO 2023-06-15T00:00:00Z]'),
        (
            datetime.fromisoformat('2023-01-31'),
            datetime.fromisoformat('2023-06-15'),
            '[2023-01-31T00:00:00Z TO 2023-06-15T00:00:00Z]',
        ),
    ]
)
def test_solr_date_range(timestamp_from, timestamp_until, expected):
    date_range = solr_date_range(timestamp_from, timestamp_until)
    assert date_range == expected


def test_index_with_solr_client(mock_solr_client):
    index = Index(config=DEFAULT_SOLR_CONFIG, solr_client=mock_solr_client)
    assert index.solr is mock_solr_client


def test_index_accessors(mock_solr_client):
    index = Index(config=DEFAULT_SOLR_CONFIG, solr_client=mock_solr_client)
    assert index.base_query == DEFAULT_SOLR_CONFIG['base_query']
    assert index.uri_field == DEFAULT_SOLR_CONFIG['uri_field']
    assert index.handle_field == DEFAULT_SOLR_CONFIG['handle_field']
    assert index.last_modified_field == DEFAULT_SOLR_CONFIG['last_modified_field']
    assert len(index.auto_set_config) == 0
    assert len(index.get_sets()) == 0


@pytest.fixture
def mock_facets_result():
    return MagicMock(
        spec=pysolr.Results,
        facets={
            'facet_fields': {
                'collection_title_facet': [
                    'Foo Collection', 12,
                    'Bar Stuff', 17,
                ]
            }
        }
    )


def test_auto_create_sets(mock_solr_client, mock_facets_result):
    mock_solr_client.search = MagicMock(return_value=mock_facets_result)
    index = Index(
        config={
            **DEFAULT_SOLR_CONFIG,
            'auto_create_sets': True,
            'auto_set': {
                'query': 'component:Collection',
                'name_field': 'display_title',
                'name_query_field': 'collection_title_facet',
            }
        },
        solr_client=mock_solr_client,
    )
    sets = index.get_sets()
    assert len(sets) == 2
    assert sets.keys() == {'foo_collection', 'bar_stuff'}


def test_search_solr_error(mock_solr_client):
    mock_solr_client.search = MagicMock(side_effect=pysolr.SolrError)
    index = Index(config=DEFAULT_SOLR_CONFIG, solr_client=mock_solr_client)
    with pytest.raises(OAIRepoExternalException):
        index.search(q='*:*')


def test_get_sets_missing_auto_set_config(mock_solr_client):
    with pytest.raises(OAIRepoInternalException):
        index = Index(
                    config={**DEFAULT_SOLR_CONFIG, 'auto_create_sets': True},
                    solr_client=mock_solr_client,
                )
        index.get_sets()


def test_get_set(mock_solr_client):
    index = Index(
        config={**DEFAULT_SOLR_CONFIG, 'sets': [{'spec': 'foo', 'name': 'Foo!', 'filter': 'title:Foo'}]},
        solr_client=mock_solr_client,
    )
    set_conf = index.get_set('foo')
    assert set_conf['spec'] == 'foo'
    assert set_conf['name'] == 'Foo!'
    assert set_conf['filter'] == 'title:Foo'


def test_get_sets_for_handle(mock_solr_client):
    mock_solr_client.search = MagicMock(side_effect=[[], {'id': 'bar'}, []])
    index = Index(
        config={
            **DEFAULT_SOLR_CONFIG,
            'sets': [
                {'spec': 'foo', 'name': 'Foo!', 'filter': 'title:Foo'},
                {'spec': 'bar', 'name': 'Bar!', 'filter': 'title:Bar'},
                {'spec': 'baz', 'name': 'Baz!', 'filter': 'title:Baz'},
            ],
        },
        solr_client=mock_solr_client,
    )
    sets = index.get_sets_for_handle('some/handle')
    assert len(sets) == 1
    assert sets.keys() == {'bar'}
