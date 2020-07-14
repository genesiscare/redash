from .elasticsearch import Elasticsearch, ElasticsearchOpenDistroSQL
from . import register

try:
    from requests_aws_sign import AWSV4Sign
    from botocore import session, credentials

    enabled = True
except ImportError:
    enabled = False


class AmazonElasticsearchServiceMixin:

    @classmethod
    def enabled(cls):
        return enabled

    @classmethod
    def configuration_schema(cls):
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "title": "Endpoint"},
                "region": {"type": "string"},
                "access_key": {"type": "string", "title": "Access Key"},
                "secret_key": {"type": "string", "title": "Secret Key"},
                "use_aws_iam_profile": {
                    "type": "boolean",
                    "title": "Use AWS IAM Profile",
                },
            },
            "order": [
                "url",
                "region",
                "access_key",
                "secret_key",
                "use_aws_iam_profile",
            ],
            "required": ["url", "region"],
            "secret": ["secret_key"],
        }

    def get_aws_auth(self, configuration):
        if configuration.get("use_aws_iam_profile", False):
            cred = credentials.get_credentials(session.Session())
        else:
            cred = credentials.Credentials(
                access_key=configuration.get("access_key", ""),
                secret_key=configuration.get("secret_key", ""),
            )
        return AWSV4Sign(cred, configuration["region"], "es")


class AmazonElasticsearchService(AmazonElasticsearchServiceMixin, Elasticsearch):

    @classmethod
    def name(cls):
        return "Amazon Elasticsearch Service"

    @classmethod
    def type(cls):
        return "aws_es"

    def __init__(self, configuration):
        super(AmazonElasticsearchService, self).__init__(configuration)
        self.auth = self.get_aws_auth(configuration)


class AmazonElasticsearchServiceSQL(AmazonElasticsearchServiceMixin, ElasticsearchOpenDistroSQL):

    @classmethod
    def name(cls):
        return "Amazon Elasticsearch Service (SQL)"

    @classmethod
    def type(cls):
        return "aws_es_sql"

    def __init__(self, configuration):
        super(AmazonElasticsearchServiceSQL, self).__init__(configuration)
        self.auth = self.get_aws_auth(configuration)


register(AmazonElasticsearchService)
register(AmazonElasticsearchServiceSQL)
