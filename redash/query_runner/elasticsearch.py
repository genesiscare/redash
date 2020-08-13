import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from redash.query_runner import TYPE_BOOLEAN, TYPE_DATE, TYPE_DATETIME, TYPE_FLOAT, TYPE_INTEGER, TYPE_STRING
from redash.query_runner import BaseHTTPQueryRunner, register
from redash.utils import json_dumps, json_loads


logger = logging.getLogger(__name__)

ELASTICSEARCH_TYPES_MAPPING = {
    "integer": TYPE_INTEGER,
    "long": TYPE_INTEGER,
    "float": TYPE_FLOAT,
    "double": TYPE_FLOAT,
    "boolean": TYPE_BOOLEAN,
    "string": TYPE_STRING,
    "date": TYPE_DATE,
    "datetime": TYPE_DATETIME,
    "object": TYPE_STRING,
}
TYPES_MAP = {
    str: TYPE_STRING,
    int: TYPE_INTEGER,
    float: TYPE_FLOAT,
    bool: TYPE_BOOLEAN,
}


class Elasticsearch(BaseHTTPQueryRunner):

    should_annotate_query = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.syntax = 'json'
        self.auth = None

    @classmethod
    def name(cls):
        return "Elasticsearch"

    def get_response(self, url, auth=None, http_method='get', **kwargs):
        url = "{}{}".format(self.configuration["url"], url)
        headers = kwargs.pop('headers', {})
        headers['Accept'] = 'application/json'
        if auth is None:
            auth = self.auth
        response, error = super().get_response(url, auth, http_method, headers=headers, verify=True, **kwargs)
        if error is not None:
            raise Exception(error)
        return response, error

    def test_connection(self) -> None:
        self.get_response("/_cluster/health")

    def get_schema(self, *args, **kwargs) -> List[Dict[str, Any]]:
        response, _ = self.get_response('/_mappings')
        mappings = self._parse_mappings(response.json())
        schema = {}
        for name, columns in mappings.items():
            schema[name] = {
                'name': name,
                'columns': list(columns.keys())
            }
        return list(schema.values())

    def run_query(self, query, user) -> Tuple[Dict[str, Any], Optional[str]]:
        query, url, result_fields = self._build_query(query)
        size = query['size']
        data: Dict[str, List[Dict[str, Any]]] = {'columns': [], 'rows': []}
        scroll_id = ""
        while True:
            if scroll_id:
                url = "/_search/scroll"
                query = {"scroll_id": scroll_id, "scroll": "1m"}
            response, error = self.get_response(url, http_method='post', json=query)
            response_json = response.json()
            if "_scroll_id" in response_json:
                scroll_id = response_json["_scroll_id"]
            more_data = self._parse_query_results(response_json, result_fields)
            data['rows'] += more_data['rows']
            if len(data['columns']) == 0:
                data['columns'] = more_data['columns']
            if len(more_data["rows"]) < size or not scroll_id:
                break
        return json_dumps(data), error

    def _parse_mappings(self, mappings_data: dict) -> Dict[str, Dict[str, str]]:
        mappings: Dict[str, Dict[str, str]] = {}

        def _parse_properties(prefix: str, properties: dict):
            for property_name, property_data in properties.items():
                if property_name not in mappings:
                    property_type = property_data.get('type', None)
                    nested_properties = property_data.get('properties', None)
                    if property_type:
                        mappings[index_name][prefix + property_name] = (
                            ELASTICSEARCH_TYPES_MAPPING.get(property_type, TYPE_STRING)
                        )
                    elif nested_properties:
                        new_prefix = prefix + property_name + '.'
                        _parse_properties(new_prefix, nested_properties)

        for index_name, index_mappings in mappings_data.items():
            if not index_name.startswith('.') and 'properties' in index_mappings['mappings']:
                mappings[index_name] = {}
                _parse_properties('', index_mappings['mappings']['properties'])

        return mappings

    def _build_query(self, query: str) -> Tuple[Dict[str, Any], str, Optional[Set[str]]]:
        q = json_loads(query)
        if 'size' not in q:
            q['size'] = 10000
        index_name = q.pop('index', '')
        url = "/{}/_search?scroll=1m".format(index_name)
        result_fields = set(q.pop('result_fields')) if 'result_fields' in q else None
        return q, url, result_fields

    def _parse_query_results(self, result: Dict[str, Any], result_fields: Optional[Set[str]] = None) -> Dict[str, Any]:
        result_columns: List[Dict[str, str]] = []
        result_rows: List[Dict[str, Any]] = []
        result_columns_index = {c["name"]: c for c in result_columns}

        def add_column_if_needed(column_name, value=None):
            if column_name not in result_columns_index:
                result_columns.append({
                    'name': column_name,
                    'friendly_name': column_name,
                    'type': TYPES_MAP.get(type(value), TYPE_STRING)
                })
                result_columns_index[column_name] = result_columns[-1]

        def get_row(rows, row):
            if row is None:
                row = {}
                rows.append(row)
            return row

        def collect_value(row, key, value):
            if result_fields and key not in result_fields:
                return
            add_column_if_needed(key, value)
            row[key] = value

        def parse_bucket_to_row(data, row, agg_key):
            sub_agg_key = ""
            for key, item in data.items():
                if key == 'key_as_string':
                    continue
                if key == 'key':
                    if 'key_as_string' in data:
                        collect_value(row, agg_key, data['key_as_string'])
                    else:
                        collect_value(row, agg_key, data['key'])
                    continue
                if isinstance(item, (str, int, float)) and key != 'doc_count':
                    collect_value(row, agg_key + '.' + key, item)
                elif isinstance(item, dict):
                    if 'buckets' not in item:
                        for sub_key, sub_item in item.items():
                            composite_key = agg_key + '.' + key
                            if sub_key != 'value':
                                composite_key += '.' + sub_key
                            collect_value(
                                row,
                                composite_key,
                                sub_item,
                            )
                    else:
                        sub_agg_key = key
            return sub_agg_key

        def parse_buckets_list(rows, parent_key, data, row, depth):
            if len(rows) > 0 and depth == 0:
                row = rows.pop()
            for value in data:
                row = row.copy()
                sub_agg_key = parse_bucket_to_row(value, row, parent_key)
                if sub_agg_key == "":
                    rows.append(row)
                else:
                    depth += 1
                    parse_buckets_list(rows, sub_agg_key, value[sub_agg_key]['buckets'], row, depth)

        def collect_aggregations(rows, parent_key, data, row, depth):
            row = get_row(rows, row)
            parse_bucket_to_row(data, row, parent_key)
            if 'buckets' in data:
                parse_buckets_list(rows, parent_key, data['buckets'], row, depth)
            return None

        def get_flatten_results(dd, separator='.', prefix=''):
            if isinstance(dd, dict):
                return {
                    prefix + separator + k if prefix else k: maybe_json_encode(v)
                    for kk, vv in dd.items()
                    for k, v in get_flatten_results(vv, separator, kk).items()
                }
            elif isinstance(dd, list) and len(dd) == 1:
                return {prefix: maybe_json_encode(dd[0])}
            else:
                return {prefix: maybe_json_encode(dd)}

        def maybe_json_encode(v):
            if isinstance(v, list) or isinstance(v, dict):
                return json.dumps(v)
            return v

        if 'error' in result:
            raise Exception(self._parse_error(result['error']))
        elif 'aggregations' in result:
            for key, data in result["aggregations"].items():
                collect_aggregations(result_rows, key, data, None, 0)
        elif 'hits' in result and 'hits' in result['hits']:
            for h in result["hits"]["hits"]:
                row = {}
                fields_parameter_name = "_source" if "_source" in h else "fields"
                for column in h[fields_parameter_name]:
                    if result_fields and column not in result_fields:
                        continue
                    unested_results = get_flatten_results({column: h[fields_parameter_name][column]})
                    for column_name, value in unested_results.items():
                        add_column_if_needed(column_name, value=value)
                        row[column_name] = value
                result_rows.append(row)
        else:
            result_string = str(result)
            if len(result_string) > 2048:
                result_string = result_string[:2048] + '...'
            raise Exception("Redash failed to parse the results it got from Elasticsearch:\n" + result_string)

        return {
            'columns': result_columns,
            'rows': result_rows
        }

    def _parse_error(self, error: Any) -> str:
        def truncate(s: str):
            if len(s) > 10240:
                s = s[:10240] + '... continues'
            return s

        if isinstance(error, dict) and 'reason' in error and 'details' in error:
            return '{}: {}'.format(truncate(error['reason']), truncate(error['details']))
        return truncate(str(error))


class ElasticsearchOpenDistroSQL(Elasticsearch):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.syntax = 'sql'

    @classmethod
    def name(cls):
        return "Elasticsearch (Open Distro SQL)"

    @classmethod
    def type(cls):
        return "elasticsearch_opendistro_sql"

    def _build_query(self, query: str) -> Tuple[Dict[str, Any], str, Optional[Set[str]]]:
        sql_query = {'query': query}
        sql_query_url = '/_opendistro/_sql?format=json'
        return sql_query, sql_query_url, None


class ElasticsearchXPackSQL(Elasticsearch):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.syntax = 'sql'

    @classmethod
    def name(cls):
        return "Elasticsearch (X-Pack SQL)"

    @classmethod
    def type(cls):
        return "elasticsearch_xpack_sql"

    def run_query(self, query, user) -> Tuple[Dict[str, Any], Optional[str]]:
        query, url, result_fields = self._build_query(query)
        response, error = self.get_response(url, http_method='post', json=query)
        response_data = response.json()
        data = self._parse_query_results(response_data, result_fields)
        columns = []
        while "cursor" in response_data:
            if "columns" in response_data:
                columns = response_data["columns"]
            query, url = self._build_cursor_query(response_data["cursor"])
            response, _ = self.get_response(url, http_method='post', json=query)
            response_data = response.json()
            response_data["columns"] = columns
            more_data = self._parse_query_results(response_data, result_fields)
            data["rows"] += more_data["rows"]
        return json_dumps(data), error

    def _build_query(self, query: str) -> Tuple[Dict[str, Any], str, Optional[Set[str]]]:
        sql_query = {'query': query}
        sql_query_url = '/_sql?format=json'
        return sql_query, sql_query_url, None

    def _build_cursor_query(self, cursor: str) -> Tuple[Dict[str, Any], str]:
        sql_query = {'cursor': cursor}
        sql_query_url = '/_sql?format=json'
        return sql_query, sql_query_url

    def _parse_query_results(self, result: Dict[str, Any], result_fields: Optional[Set[str]] = None) -> Dict[str, Any]:
        if 'error' in result:
            raise Exception(self._parse_error(result['error']))
        columns = [
            {
                'name': column['name'],
                'friendly_name': column['name'],
                'type': ELASTICSEARCH_TYPES_MAPPING.get(column['type'], 'string'),
            }
            for column in result['columns']
        ]
        rows = [
            {
                column['name']: value
                for column, value in zip(columns, row)
            }
            for row in result['rows']
        ]
        return {
            'columns': columns,
            'rows': rows,
        }


register(Elasticsearch)
register(ElasticsearchOpenDistroSQL)
register(ElasticsearchXPackSQL)
