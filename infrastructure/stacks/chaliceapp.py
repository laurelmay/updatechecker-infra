import os

from aws_cdk import (
    aws_certificatemanager as acm,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_route53 as dns,
    aws_sns as sns,
    core as cdk,
)
import jsii
from chalice.cdk import Chalice


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, "runtime"
)


@jsii.implements(dns.IAliasRecordTarget)
class ChaliceCustomDomain:
    def __init__(self, apigw_domain: apigw.CfnDomainName):
        self.dns_name = apigw_domain.attr_distribution_domain_name
        self.hosted_zone_id = apigw_domain.attr_distribution_hosted_zone_id

    def bind(self, record, zone):
        return dns.AliasRecordTargetConfig(
            dns_name=self.dns_name, hosted_zone_id=self.hosted_zone_id
        )


class ChaliceApp(cdk.Stack):
    def __init__(self, scope, id, domain_name=None, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.dynamodb_table = self._create_ddb_table()
        self.sns_topic = self._create_sns_topic()
        stage_config = {
            "environment_variables": {
                "APP_TABLE_NAME": self.dynamodb_table.table_name,
                "APP_TABLE_STREAM": self.dynamodb_table.table_stream_arn,
                "NOTIFY_TOPIC": self.sns_topic.topic_arn,
            },
            "automatic_layer": True,
            "lambda_memory_size": 384,
            "xray": True,
        }
        if domain_name:
            self.api_fqdn = f"updatechecker.{domain_name}"
            zone = self._get_hosted_zone(domain_name)
            self.certificate = self._create_certificate(zone)
            stage_config["api_gateway_custom_domain"] = {
                "domain_name": self.api_fqdn,
                "certificate_arn": self.certificate.certificate_arn,
            }
        self.chalice = Chalice(
            self,
            "ChaliceApp",
            source_dir=RUNTIME_SOURCE_DIR,
            stage_config=stage_config,
        )
        self.dynamodb_table.grant_read_write_data(self.chalice.get_role("DefaultRole"))
        self.dynamodb_table.grant_stream_read(self.chalice.get_role("DefaultRole"))
        self.sns_topic.grant_publish(self.chalice.get_role("DefaultRole"))

        if domain_name:
            self._create_dns_records(zone)

    def _get_hosted_zone(self, domain_name):
        return dns.HostedZone.from_lookup(self, "DomainDns", domain_name=domain_name)

    def _create_certificate(self, hosted_zone):
        return acm.DnsValidatedCertificate(
            self, "Certificate", hosted_zone=hosted_zone, domain_name=self.api_fqdn
        )

    def _create_dns_records(self, zone):
        apigw_domain: apigw.CfnDomainName = self.chalice.get_resource(
            "ApiGatewayCustomDomain"
        )
        target = dns.RecordTarget.from_alias(ChaliceCustomDomain(apigw_domain))
        dns.ARecord(
            self, "ApiGwAlias", zone=zone, target=target, record_name=self.api_fqdn
        )
        dns.AaaaRecord(
            self, "ApiGwAaaalias", zone=zone, target=target, record_name=self.api_fqdn
        )

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
