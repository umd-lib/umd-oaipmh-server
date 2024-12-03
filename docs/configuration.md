# Configuration

The umd-fcrepo-oaipmh server is configured in two ways: environment
variables for the service itself, and a YAML configuration file to define
the queries and fields it uses when making Solr requests.

## Environment Variables

| Name                       | Default Value          |
|----------------------------|------------------------|
| `ADMIN_EMAIL`              |                        |
| `BASE_URL`                 | http://localhost:5000/ |
| `DATESTAMP_GRANULARITY`    | YYYY-MM-DDThh:mm:ssZ   |
| `EARLIEST_DATESTAMP`       |                        |
| `JWT_SECRET`               |                        |
| `OAI_NAMESPACE_IDENTIFIER` |                        |
| `OAI_REPOSITORY_NAME`      |                        |
| `PAGE_SIZE`                | 25                     |
| `REPORT_DELETED_RECORDS`   | no                     |
| `SOLR_URL`                 |                        |

### `ADMIN_EMAIL`

Administrator email to publish as part of the Identify information.

See also: [OAI-PMH Specification § 4.2 Identify]

### `BASE_URL`

Base URL of the application. Defaults to `http://localhost:5000/`.

See also: [OAI-PMH Specification § 4.2 Identify]

### `DATESTAMP_GRANULARITY`

The level of specificity at which datestamp filters can be applied.
Allowed values are:

* `YYYY-MM-DDThh:mm:ssZ`
* `YYYY-MM-DD`

Defaults to `YYYY-MM-DDThh:mm:ssZ`.

See also: [OAI-PMH Specification § 3.3 UTCDatetime]

### `EARLIEST_DATESTAMP`

The earliest datestamp for which metadata or records can be retrieved.

See also: [OAI-PMH Specification § 4.2 Identify]

### `JWT_SECRET`

JWT secret for the server to generate its own token to access the fcrepo repository.

### `OAI_NAMESPACE_IDENTIFIER`

String to use as the namespace segment of an [OAI identifier].

### `OAI_REPOSITORY_NAME`

Name of the OAI-PMH service to be published as part of the Identify response.

See also: [OAI-PMH Specification § 4.2 Identify]

### `PAGE_SIZE`

Number of records to include on each page. Defaults to 25.

### `REPORT_DELETED_RECORDS`

Whether this service supports publishing notifications of record deletion.
Allowed values are `yes` and `no`. Defaults to `no`.

**Note:** This implementation currently does not support this feature, and
while setting this to `yes` will change the response to the Identify
request, it will not actually enable publication of deleted record notices.

See also: [OAI-PMH Specification § 4.2 Identify]

### `SOLR_URL`

Solr index to query for record metadata.

## Configuration File

Configuration of the queries and fields to use with Solr is done via a
YAML configuration file. Here is an example for fedora:

```yaml
base_query: item__handle__id:*
handle_field: item__handle__id
uri_field: id
last_modified_field: item__last_modified__dt
auto_create_sets: True
auto_set:
  query: resource_type__facet:Collection
  name_field: item__title__txt
  name_query_field: admin_set__facet
sets:
  - spec: custom_set
    name: Custom Collection
    filter: presentation_set__facet:Foo AND resource_type__facet:Issue
```

And here is an example for avalon:

```yaml
base_query: has_model_ssim:MediaObject AND avalon_publisher_ssi:* AND hidden_bsi:false
handle_field: permalink_tesim
uri_field: id
last_modified_field: system_modified_dtsi
auto_create_sets: True
auto_set:
  query: has_model_ssim:"Admin::Collection"
  name_field: name_ssi
  name_query_field: collection_ssim
sets: []
```

### `base_query`

Solr query used as the starting point for all queries. Without further
modifications, this should return results for all harvestable records in
the index.

### `handle_field`

Name of the Solr field that stores the handle, in `{prefix}/{local}`
format.

### `uri_field`

Name of the Solr field that stores the URI of the resource in fcrepo.

### `last_modified_field`

Name of the Solr field that stores the last-modified timestamp for the
resource.

### `auto_create_sets`

Whether to dynamically create set definitions from a Solr query.

### `auto_sets`

More options for dynamically creating sets.

#### `query`

Solr query to return a list of resources that should be converted to sets.

#### `name_field`

Name of the Solr field to use as the set name. The set spec value is
constructed from the name by converting it to lowercase and replacing all
non-alphanumeric characters with underscores.

#### `name_query_field`

Name of the Solr field appearing in record documents that will contain the
name of the dynamically created set.

### `sets`

Zero or more static definitions of sets. Each set has the following keys:

#### `spec`

The short, all lowercase, alphanumeric-and-underscore-only code for the set.

#### `name`

The human-readable name for the set.

#### `filter`

Solr query expression to select all documents belonging to this set.

[OAI-PMH Specification § 3.3 UTCDatetime]: http://www.openarchives.org/OAI/openarchivesprotocol.html#Dates
[OAI-PMH Specification § 4.2 Identify]: http://www.openarchives.org/OAI/openarchivesprotocol.html#Identify
[OAI identifier]: http://www.openarchives.org/OAI/2.0/guidelines-oai-identifier.htm
