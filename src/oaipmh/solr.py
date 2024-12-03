import logging
from datetime import datetime
from typing import Any, Optional, Mapping

import pysolr
from oai_repo import OAIRepoExternalException
from oai_repo.exceptions import OAIErrorBadArgument, OAIRepoInternalException
from oai_repo.helpers import datestamp_long

from oaipmh.oai import get_set_spec

logger = logging.getLogger(__name__)


class Index:
    def __init__(self, config: dict[str, Any], solr_client: pysolr.Solr):
        self.config = config
        self.solr = solr_client
        logger.info(f'Solr URL: {self.solr.url}')
        logger.debug(f'Index configuration: {config}')
        logger.debug(f'All sets: {self.get_sets()}')

    @property
    def auto_create_sets(self):
        return self.config['auto_create_sets']

    @property
    def auto_set_config(self):
        return self.config.get('auto_set', {})

    @property
    def base_query(self):
        return self.config['base_query']

    @property
    def handle_field(self):
        return self.config['handle_field']

    @property
    def uri_field(self):
        return self.config['uri_field']

    @property
    def last_modified_field(self):
        return self.config['last_modified_field']

    def search(self, **kwargs):
        try:
            return self.solr.search(**kwargs)
        except pysolr.SolrError as e:
            logger.error(str(e))
            raise OAIRepoExternalException('Unable to connect to Solr') from e

    def get_handle(self, doc: Mapping[str, Any]) -> str:
        handle = doc[self.handle_field]
        return handle[0] if isinstance(handle, list) else str(handle)

    def get_sets(self) -> dict[str, dict[str, str]]:
        sets = {s['spec']: s for s in self.config['sets']}

        if self.auto_create_sets:
            try:
                facet_field = self.auto_set_config['name_query_field']
                results = self.search(
                    q=self.base_query,
                    rows=0,
                    facet='on',
                    **{
                        'facet.field': facet_field,
                        'facet.mincount': 1,
                    })
            except KeyError as e:
                logger.error(f'Missing auto_set_config key {e}')
                raise OAIRepoInternalException('Configuration error') from e

            # slice by every second element to get the even-indexed elements (i.e., the facet names)
            facets = results.facets['facet_fields'][facet_field][::2]

            for name in facets:
                spec = get_set_spec(name)
                sets[spec] = {
                    'spec': spec,
                    'name': name,
                    'filter': f"{facet_field}:{solr_quoted(name)}"
                }

        return sets

    def get_set(self, spec: str) -> dict[str, str]:
        return self.get_sets()[spec]

    def get_sets_for_handle(self, handle: str) -> dict[str, dict[str, str]]:
        sets = {}
        for set_spec, set_conf in self.get_sets().items():
            result = self.solr.search(q=f'{self.handle_field}:{solr_quoted(handle)}', fq=set_conf['filter'], fl=self.uri_field)
            if len(result):
                sets[set_spec] = set_conf
        return sets

    def get_docs(
            self,
            filter_from: Optional[datetime] = None,
            filter_until: Optional[datetime] = None,
            filter_set: Optional[str] = None,
            start: Optional[int] = 0,
            rows: Optional[int] = 25,
    ):
        filter_query = self.base_query
        if filter_from or filter_until:
            datetime_range = solr_date_range(filter_from, filter_until)
            filter_query += f' AND {self.last_modified_field}:{datetime_range}'
        if filter_set:
            try:
                filter_query += f' AND ({self.get_sets()[filter_set]["filter"]})'
            except KeyError:
                raise OAIErrorBadArgument(f"'{filter_set}' is not a valid setSpec value")
        logger.debug(f'Solr fq = "{filter_query}"')

        return self.search(q='*:*', fq=filter_query, start=start, rows=rows)

    def get_doc(self, handle: str) -> dict[str, Any]:
        results = self.search(q=f'{self.handle_field}:{solr_quoted(handle)}')
        if not results:
            raise OAIRepoExternalException(f'Unable to find handle {handle} in Solr')
        return results.docs[0]


def solr_quoted(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def solr_date_range(timestamp_from: Optional[datetime], timestamp_until: Optional[datetime]) -> str:
    try:
        datestamp_from = datestamp_long(timestamp_from) if timestamp_from else '*'
        datestamp_until = datestamp_long(timestamp_until) if timestamp_until else '*'
    except AttributeError as e:
        raise TypeError("'timestamp_from' and 'timestamp_until', if present, must be datetime objects") from e
    return f'[{datestamp_from} TO {datestamp_until}]'
