FROM python:3.11.2-slim

EXPOSE 5000

WORKDIR /opt/umd-fcrepo-oaipmh

COPY requirements.txt /opt/umd-fcrepo-oaipmh/
RUN pip install -r requirements.txt
COPY src pyproject.toml /opt/umd-fcrepo-oaipmh/
RUN pip install -e .

ENTRYPOINT ["fcrepo-oaipmh-server"]
