FROM python:3.11-slim-bookworm

# Install git
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean

# The base image's pip bundles an outdated CA file; upgrade it, verifying the download against the OS store
RUN PIP_CERT=/etc/ssl/certs/ca-certificates.crt pip install --no-cache-dir --upgrade "pip>=26.2.2"

EXPOSE 5000

WORKDIR /opt/umd-fcrepo-oaipmh

# Copy project
# This all git tracked files will be copied, so that
# the version can be derived without any git diffs
COPY --exclude=.git . .

# Temporarily mount the .git folder to infer the version during installation
RUN --mount=source=.git,target=.git,type=bind \
    pip install -e .

ENTRYPOINT ["fcrepo-oaipmh-server"]
