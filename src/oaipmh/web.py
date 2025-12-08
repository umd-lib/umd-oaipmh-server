from os import environ
from re import match
from http import HTTPStatus
from typing import Any, Optional, TextIO

import pysolr
import yaml
from flask import Flask, request, abort, redirect, url_for
from lxml import etree
# noinspection PyProtectedMember
from lxml.etree import ElementTree, _ElementTree
from oai_repo.repository import OAIRepository
from oai_repo.exceptions import OAIRepoInternalException, OAIRepoExternalException
from oai_repo.response import OAIResponse

from oaipmh import __version__
from oaipmh.dataprovider import DataProvider, FedoraDataProvider, DataProviderType
from oaipmh.solr import Index


def status(response: OAIResponse) -> int:
    """Get the HTTP status code to return with the given OAI response."""

    # the OAIResponse casts to boolean "False" on error
    if response:
        return HTTPStatus.OK
    else:
        error = response.xpath('/OAI-PMH/error')[0]
        if error.get('code') in {'noRecordsMatch', 'idDoesNotExist'}:
            return HTTPStatus.NOT_FOUND
        else:
            return HTTPStatus.BAD_REQUEST


def get_config(config_source: Optional[str | TextIO] = None) -> dict[str, Any]:
    if config_source is None:
        raise RuntimeError("Must specify a configuration file")
    if isinstance(config_source, str):
        with open(config_source) as fh:
            return yaml.safe_load(fh)
    if config_source:
        return yaml.safe_load(config_source)


def app(solr_config_file: Optional[str] = None, data_provider_type: Optional[str] = None) -> Flask:
    index = Index(
        config=get_config(solr_config_file),
        solr_client=pysolr.Solr(environ['SOLR_URL']),
    )

    try:
        if data_provider_type is None:
            data_provider = DataProviderType[environ['DATA_PROVIDER_TYPE']].value(index=index)
        else:
            data_provider = DataProviderType[data_provider_type].value(index=index)
    except KeyError:
        raise RuntimeError(f'"{data_provider_type}" is not a valid data provider type')

    return create_app(data_provider)


def create_app(data_provider: DataProvider) -> Flask:
    _app = Flask(
        import_name=__name__,
        static_url_path='/oai/static',
    )
    _app.logger.info(f'Starting umd-fcrepo-oaipmh/{__version__}')
    _app.logger.debug(f'Initialized the data provider: {data_provider.get_identify()}')
    use_xsl_stylesheet = bool(environ.get('XSL_STYLESHEET'))

    @_app.route('/')
    def root():
        return redirect(url_for('home'))

    @_app.route('/oai')
    def home():
        identify_url = data_provider.base_url + '?verb=Identify'
        return f"""
        <h1>OAI-PMH Service for {environ['DATA_PROVIDER_TYPE'].capitalize()}: {data_provider.oai_repository_name}</h1>
        <ul>
          <li>Version: umd-oaipmh-server/{__version__}</li>
          <li>Endpoint: {data_provider.base_url}</li>
          <li>Identify: <a href="{identify_url}">{identify_url}</a></li>
        </ul>
        <p>See the <a href="http://www.openarchives.org/OAI/openarchivesprotocol.html" target="_blank">OAI-PMH
        Protocol 2.0 Specification</a> for information about how to use this service.</p>
        """

    @_app.route('/oai/api', methods=['GET', 'POST'])
    def endpoint():
        try:
            repo = OAIRepository(data_provider)
            # combine all possible parameters to the request
            parameters = {
                **request.args,
                **request.form,
            }

            if 'until' in parameters and match(r'^\d\d\d\d-\d\d-\d\d$', parameters['until']):
                parameters['until'] += 'T23:59:59Z'

            response = repo.process(parameters)
        except OAIRepoExternalException as e:
            # An API call timed out or returned a non-200 HTTP code.
            # Log the failure and abort with server HTTP 503.
            _app.logger.error(f'Upstream error: {e}')
            abort(HTTPStatus.SERVICE_UNAVAILABLE, str(e))
        except OAIRepoInternalException as e:
            # There is a fault in how the DataInterface was implemented.
            # Log the failure and abort with server HTTP 500.
            _app.logger.error(f'Internal error: {e}')
            abort(HTTPStatus.INTERNAL_SERVER_ERROR)
        else:
            document: _ElementTree = ElementTree(response.root())
            if use_xsl_stylesheet:
                stylesheet = etree.ProcessingInstruction('xml-stylesheet', 'type="text/xsl" href="static/html.xsl"')
                document.getroot().addprevious(stylesheet)
            return (
                etree.tostring(document, xml_declaration=True, encoding='UTF-8', pretty_print=True),
                status(response),
                {'Content-Type': 'application/xml'},
            )

    return _app
