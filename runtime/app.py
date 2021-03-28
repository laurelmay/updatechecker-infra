import json
import os

import boto3
import requests
from chalice import Chalice, NotFoundError
from chalice.app import Rate
from updatechecker import checkers

from chalicelib import helpers

app = Chalice(app_name='updatecheckerv2')
dynamodb = boto3.resource('dynamodb')
sns = boto3.resource('sns')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
dynamodb_stream = os.environ.get('APP_TABLE_STREAM', '')
notify_topic = sns.Topic(os.environ.get('NOTIFY_TOPIC', ''))


@app.route('/software')
def list_software():
    full_data = dynamodb_table.scan()['Items']
    software_list = list(set([item['id'] for item in full_data]))
    return {'software': software_list}


@app.route('/software/{name}')
def get_latest_software(name):
    item = helpers.get_software_version(dynamodb_table, name, 'latest')
    if not item:
        raise NotFoundError(f"Cannot find latest {name}")
    return item


@app.route('/software/{name}/{version}')
def get_software_version(name, version):
    item = helpers.get_software_version(dynamodb_table, name, version)
    if not item:
        raise NotFoundError(f"Cannot find {name} {version}")
    return item


@app.schedule(Rate(2, Rate.HOURS))
def update_data(event):
    session = requests.Session()
    session.headers.update({'User-Agent': 'Update checking tool'})
    data = []
    for _, checker in checkers.all_checkers().items():
        data.append(checker({}, session, False))
        data[-1].load()
    for checked in data:
        updated = helpers.set_version_data(dynamodb_table, checked)
        if updated:
            helpers.set_version_data(dynamodb_table, checked, 'latest')


@app.on_dynamodb_record(dynamodb_stream)
def send_update_notification(event):
    updates = []
    for record in event:
        # Skip delete events and events for the non-latest
        if record.event_name == 'DELETE':
            app.log.info("Skipping delete event")
            continue
        if not record.keys['SK']['S'].endswith('latest'):
            continue
        if not record.new_image:
            app.log.warn(
                "Got a MODIFY/INSERT without new_image: %s",
                record.to_dict()
            )
            continue
        updates.append(record.new_image)
    if not updates:
        return
    for update in updates:
        app.log.debug(json.dumps(update, indent=4))
        helpers.send_update_message(notify_topic, update)
