import asyncio
import json
import logging

from datetime import date, datetime
from typing import Any, Dict

import aiohttp
from botocore.exceptions import ClientError

from updatechecker import checkers

_LOGGER = logging.getLogger("updatecheckerv2")


def primary_key(name: str) -> str:
    """
    Format the given software name as an app primary key.
    """
    return f"Software#{name}"


def sort_key(version: str) -> str:
    """
    Format the given software version as an app sort key.
    """
    return f"Version#{version}"


def process_item(item: Dict[str, Any]):
    """
    Process the given item appropriately so that it may be displayed to
    a user.
    """
    del item["PK"]
    del item["SK"]
    return item


async def refresh_data(table, error_topic, logger):
    """
    Update the cached data about software version.
    """
    headers = {"User-Agent": "Update Checker tool <updatechecker@laker.email>"}
    async with aiohttp.ClientSession(headers=headers, raise_for_status=True) as session:
        checks = [checker(session, False) for _, checker in checkers.all_checkers().items()]
        results = await asyncio.gather(*[checker.load() for checker in checks], return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.exception(
                    "Handled error checking for %s", checks[idx].name, exc_info=result
                )
                send_error_message(error_topic, checks[idx].name, result)
                continue
            updated = set_version_data(table, result)
            if updated:
                set_version_data(table, result, "latest")


def get_software_version(table, name, version):
    """
    Get a specific version of the given software.
    """
    key = {"PK": primary_key(name), "SK": sort_key(version)}
    try:
        item = table.get_item(Key=key)["Item"]
    except (ClientError, KeyError):
        return None
    process_item(item)
    return item


def get_all_versions(table, name):
    """
    Get a list of all actual versions of the given software.

    The "latest" alias is not returned.
    """
    key_conditions = {
        "PK": {"ComparisonOperator": "EQ", "AttributeValueList": [primary_key(name)]},
    }
    try:
        response = table.query(KeyConditions=key_conditions)
    except ClientError as client_err:
        _LOGGER.error("Unable to complete query for %s", name, exc_info=client_err)
        raise

    items = [
        process_item(item)
        for item in response.get("Items", [])
        if not item["SK"] == sort_key("latest")
    ]
    if not items:
        _LOGGER.info(
            "No items for query: %s. Response: %s",
            json.dumps(key_conditions),
            json.dumps(response, default=str),
        )
        return None

    return items


def set_version_data(table, data, version=None):
    """
    Update the table to add information about a particular version.
    """
    if not version:
        version = data.latest_version
    latest_key = {"PK": primary_key(data.short_name), "SK": sort_key(version)}
    item = {
        ":i": data.short_name,
        ":n": data.name,
        ":v": data.latest_version,
        ":u": data.latest_url,
        ":s": data.sha1_hash,
        ":t": datetime.utcnow().isoformat(),
    }
    name_transforms = {"#n": "name", "#u": "url", "#t": "timestamp"}
    try:
        response = table.update_item(
            Key=latest_key,
            UpdateExpression="SET id=:i, #n=:n, version=:v, #u=:u, sha1=:s, #t=:t",
            ExpressionAttributeValues=item,
            ExpressionAttributeNames=name_transforms,
            ConditionExpression=f"version <> :v OR #u <> :u OR sha1 <> :s",
            ReturnValues="UPDATED_NEW",
        )
    except ClientError as e:
        if "ConditionalCheckFailedException" not in str(e):
            raise
        return None

    return response


def send_update_message(topic, update):
    """
    Send a message about a software update to SNS.
    """
    message_lines = [
        f"A new version of {update['name']['S']} is available:",
        f"    Version: {update['version']['S']}",
        f"    URL: {update['url']['S']}",
        f"    SHA1: {update['sha1']['S']}",
    ]
    subject = f"{update['name']['S']} update available"
    topic.publish(Subject=subject, Message="\n".join(message_lines))


def send_error_message(topic, software, error):
    """
    Send a message when an error occurs during an update.
    """
    message_lines = [
        f"An error occurred checking for {software} updates.",
        "",
        "Error:",
        f"{str(error)}",
    ]
    subject = f"Failed to check updates for {software}"
    topic.publish(Subject=subject, Message="\n".join(message_lines))
