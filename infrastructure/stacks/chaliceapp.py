import os

from aws_cdk import aws_dynamodb as dynamodb, aws_sns as sns, core as cdk
import chalice
from chalice.cdk import Chalice


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


class ChaliceApp(cdk.Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.dynamodb_table = self._create_ddb_table()
        self.sns_topic = self._create_sns_topic()
        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                "environment_variables": {
                    "APP_TABLE_NAME": self.dynamodb_table.table_name,
                    "APP_TABLE_STREAM": self.dynamodb_table.table_stream_arn,
                    "NOTIFY_TOPIC": self.sns_topic.topic_arn,
                },
                "automatic_layer": True,
                "lambda_memory_size": 384,
            },
        )
        self.dynamodb_table.grant_read_write_data(self.chalice.get_role("DefaultRole"))
        self.dynamodb_table.grant_stream_read(self.chalice.get_role("DefaultRole"))
        self.sns_topic.grant_publish(self.chalice.get_role("DefaultRole"))

    def _create_sns_topic(self):
        sns_topic = sns.Topic(
            self,
            "NotifyTopic",
            display_name="Update notifications",
        )
        cdk.CfnOutput(self, "NotifyTopicArn", value=sns_topic.topic_arn)
        return sns_topic

    def _create_ddb_table(self):
        dynamodb_table = dynamodb.Table(
            self,
            "VersionTable",
            billing_mode=dynamodb.BillingMode.PROVISIONED,
            read_capacity=1,
            write_capacity=1,
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            removal_policy=cdk.RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_IMAGE,
        )
        cdk.CfnOutput(self, "AppTableName", value=dynamodb_table.table_name)
        return dynamodb_table
