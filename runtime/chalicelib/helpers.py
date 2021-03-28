from datetime import date, datetime
from botocore.exceptions import ClientError

def get_software_version(table, name, version):
    key = {
        'PK': f'Software#{name}',
        'SK': f'Version#{version}'
    }
    try:
        item = table.get_item(Key=key)['Item']
    except (ClientError, KeyError):
        return None
    del item['PK']
    del item['SK']
    return item

def set_version_data(table, data, version=None):
    if not version:
        version = data.latest_version
    latest_key = {
        'PK': f"Software#{data.short_name}",
        'SK': f"Version#{version}"
    }
    item = {
        ":i": data.short_name,
        ":n": data.name,
        ":v": data.latest_version,
        ":u": data.latest_url,
        ":s": data.sha1_hash,
        ":t": datetime.utcnow().isoformat(),
    }
    name_transforms = {
        "#n": "name",
        "#u": "url",
        "#t": "timestamp"
    }
    try:
        response = table.update_item(
            Key=latest_key,
            UpdateExpression="SET id=:i, #n=:n, version=:v, #u=:u, sha1=:s, #t=:t",
            ExpressionAttributeValues=item,
            ExpressionAttributeNames=name_transforms,
            ConditionExpression=f"version <> :v OR #u <> :u OR sha1 <> :s",
            ReturnValues="UPDATED_NEW"
        )
    except ClientError as e:
        if 'ConditionalCheckFailedException' not in str(e):
            raise
        return None

    return response

def send_update_message(topic, update):
    message_lines = [
        f"A new version of {update['name']['S']} is available:",
        f"    Version: {update['version']['S']}",
        f"    URL: {update['url']['S']}",
        f"    SHA1: {update['sha1']['S']}",
    ]
    subject = f"{update['name']['S']} update available"
    topic.publish(Subject=subject, Message="\n".join(message_lines))
