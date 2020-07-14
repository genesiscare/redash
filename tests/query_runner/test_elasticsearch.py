from unittest import TestCase

from redash.query_runner.elasticsearch import Elasticsearch


class TestElasticSearch(TestCase):

    def test_parse_mappings(self):
        mapping_data = {
            "bank": {
                "mappings": {
                    "properties": {
                        "account_number": {
                            "type": "long"
                        },
                        "balance": {
                            "type": "long"
                        },
                        "city": {
                            "fields": {
                                "keyword": {
                                    "ignore_above": 256,
                                    "type": "keyword"
                                }
                            },
                            "type": "text"
                        },
                        "geo": {
                            "properties": {
                                "lat": {
                                    "type": "long"
                                },
                                "long": {
                                    "type": "long"
                                }
                            }
                        },
                    }
                }
            }
        }
        expected = {
            'bank': {
                'account_number': 'integer',
                'balance': 'integer',
                'city': 'string',
                'geo.lat': 'integer',
                'geo.long': 'integer'
            }
        }
        self.assertDictEqual(Elasticsearch._parse_mappings(mapping_data), expected)

    def test_parse_aggregation(self):
        response = {
            "took": 3,
            "timed_out": False,
            "_shards": {
                "total": 1,
                "successful": 1,
                "skipped": 0,
                "failed": 0
            },
            "hits": {
                "total": {
                    "value": 1001,
                    "relation": "eq"
                },
                "max_score": None,
                "hits": []
            },
            "aggregations": {
                "group_by_state": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 743,
                    "buckets": [
                        {
                            "key": "TX",
                            "doc_count": 30
                        },
                        {
                            "key": "MD",
                            "doc_count": 28
                        },
                        {
                            "key": "ID",
                            "doc_count": 27
                        },
                    ]
                }
            }
        }
        expected = {
            'columns': [
                {
                    'friendly_name': 'group_by_state',
                    'name': 'group_by_state',
                    'type': 'string'
                },
                {
                    'friendly_name': 'group_by_state.doc_count',
                    'name': 'group_by_state.doc_count',
                    'type': 'integer'
                }
            ],
            'rows': [
                {
                    'group_by_state': 'TX',
                    'group_by_state.doc_count': 30,
                },
                {
                    'group_by_state': 'MD',
                    'group_by_state.doc_count': 28,
                },
                {
                    'group_by_state': 'ID',
                    'group_by_state.doc_count': 27,
                }
            ]
        }
        fields = ['group_by_state', 'group_by_state.doc_count']
        self.assertDictEqual(Elasticsearch._parse_results(fields, response), expected)

    def test_parse_sub_aggregation(self):
        response = {
            "took": 2,
            "timed_out": False,
            "_shards": {
                "total": 1,
                "successful": 1,
                "skipped": 0,
                "failed": 0
            },
            "hits": {
                "total": {
                    "value": 1001,
                    "relation": "eq"
                },
                "max_score": None,
                "hits": []
            },
            "aggregations": {
                "group_by_state": {
                    "doc_count_error_upper_bound": -1,
                    "sum_other_doc_count": 828,
                    "buckets": [
                        {
                            "key": "CO",
                            "doc_count": 14,
                            "average_balance": {
                                "value": 32460.35714285714
                            }
                        },
                        {
                            "key": "AZ",
                            "doc_count": 14,
                            "average_balance": {
                                "value": 31634.785714285714
                            }
                        }
                    ]
                }
            }
        }
        expected = {
            'columns': [
                {
                    'friendly_name': 'group_by_state',
                    'name': 'group_by_state',
                    'type': 'string'
                },
                {
                    'friendly_name': 'group_by_state.average_balance.value',
                    'name': 'group_by_state.average_balance.value',
                    'type': 'float'
                }
            ],
            'rows': [
                {
                    'group_by_state': 'CO',
                    'group_by_state.average_balance.value': 32460.35714285714,
                },
                {
                    'group_by_state': 'AZ',
                    'group_by_state.average_balance.value': 31634.785714285714,
                },
            ]
        }
        fields = ['group_by_state', 'group_by_state.average_balance.value']
        self.assertDictEqual(Elasticsearch._parse_results(fields, response), expected)
