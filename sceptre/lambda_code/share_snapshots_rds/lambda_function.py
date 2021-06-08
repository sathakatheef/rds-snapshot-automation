# share_snapshots_rds
# This Lambda function shares the manual snapshots created by take_snapshots_rds lambda with the destination AWS account number set in the environment variable DEST_ACCOUNT
# It will only share snapshots tagged with shareAndCopy and a value of YES
import boto3
from datetime import datetime
import time
import os
import logging
import re
from snapshots_tool_utils import *

# Initialize from environment variable
LOGLEVEL = os.getenv('LOG_LEVEL', 'ERROR').strip()
DEST_ACCOUNTID = str(os.getenv('DEST_ACCOUNT')).strip()
PATTERN = os.getenv('PATTERN', 'ALL_INSTANCES')
PLATFORM = os.getenv('PLATFORM').strip()

if os.getenv('REGION_OVERRIDE', 'NO') != 'NO':
    REGION = os.getenv('REGION_OVERRIDE').strip()
else:
    REGION = os.getenv('AWS_DEFAULT_REGION')

SUPPORTED_ENGINES = [ 'mariadb', 'sqlserver-se', 'sqlserver-ee', 'sqlserver-ex', 'sqlserver-web', 'mysql', 'oracle-se', 'oracle-se1', 'oracle-se2', 'oracle-ee', 'postgres' ]

logger = logging.getLogger()
logger.setLevel(LOGLEVEL.upper())

def lambda_handler(event, context):
    pending_snapshots = 0
    client = boto3.client('rds', region_name=REGION)
    response = paginate_api_call(client, 'describe_db_snapshots', 'DBSnapshots', SnapshotType='manual')
    filtered = get_own_snapshots_source(PATTERN, response)

    # Search all snapshots for the correct tag
    for snapshot_identifier,snapshot_object in filtered.items():
        snapshot_arn = snapshot_object['Arn']
        response_tags = client.list_tags_for_resource(
            ResourceName=snapshot_arn)

        if snapshot_object['Status'].lower() == 'available' and search_tag_shared(response_tags):
            try:
                # Share snapshot with dest_account
                response_modify = client.modify_db_snapshot_attribute(
                    DBSnapshotIdentifier=snapshot_identifier,
                    AttributeName='restore',
                    ValuesToAdd=[
                        DEST_ACCOUNTID
                    ]
                )
            except Exception as e:
                logger.error('Exception sharing %s (%s)' % (snapshot_identifier, e))
                pending_snapshots += 1

    if pending_snapshots > 0:
        log_message = 'Could not share all snapshots. Pending: %s' % pending_snapshots
        logger.error(log_message)
        raise SnapshotToolException(log_message)

if __name__ == '__main__':
    lambda_handler(None, None)