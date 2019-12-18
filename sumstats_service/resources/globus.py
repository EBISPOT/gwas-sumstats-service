import os
import json
import sys
import urllib
import webbrowser
from urllib.parse import unquote
import config
import globus_sdk
from globus_sdk import (NativeAppAuthClient, TransferClient,
                        RefreshTokenAuthorizer, ConfidentialAppAuthClient)
from globus_sdk.exc import GlobusAPIError
from sumstats_service.resources.globus_utils import is_remote_session, enable_requests_logging
from pymongo import MongoClient
from bson.objectid import ObjectId


get_input = getattr(__builtins__, 'raw_input', input)
# uncomment the next line to enable debug logging for network requests
# enable_requests_logging()


def mkdir(unique_id, email_address):
    transfer = init()
    endpoint_id = create_dir(transfer, unique_id, email_address)
    return endpoint_id


def list_dir(unique_id):
    transfer = init()
    return dir_contents(transfer, unique_id)


def init():
    tokens = None
    try:
        # if we already have tokens, load and use them
        tokens = load_tokens_from_db()
    except:
        pass

    if not tokens:
        # if we need to get tokens, start the Native App authentication process
        tokens = do_native_app_authentication(config.TRANSFER_CLIENT_ID, config.REDIRECT_URI, config.SCOPES)

        try:
            save_tokens_to_db(tokens)
        except:
            pass

    transfer_tokens = tokens['transfer.api.globus.org']

    client = NativeAppAuthClient(client_id=config.TRANSFER_CLIENT_ID)

    authorizer = RefreshTokenAuthorizer(
        transfer_tokens['refresh_token'],
        client,
        access_token=transfer_tokens['access_token'],
        expires_at=transfer_tokens['expires_at_seconds'],
        on_refresh=update_tokens_file_on_refresh)

    transfer = TransferClient(authorizer=authorizer)
    prepare_call(transfer)

    return transfer


def prepare_call(transfer):
    try:
        transfer.endpoint_autoactivate(config.GWAS_ENDPOINT_ID)
    except GlobusAPIError as ex:
        print(ex)
        if ex.http_status == 401:
            sys.exit('Refresh token has expired. '
                     'Please delete refresh-tokens.json and try again.')
        else:
            raise ex
    return


def dir_contents(transfer, unique_id):
    # prepare_call(transfer)
    # print out a directory listing from an endpoint
    contents = []

    try:
        for entry in transfer.operation_ls(config.GWAS_ENDPOINT_ID, path='/~/' + unique_id):
            contents.append(entry['name'] + ('/' if entry['type'] == 'dir' else ''))
    except globus_sdk.exc.TransferAPIError:
        return None       
    return contents


def get_upload_status(transfer, unique_id, files):
    return_files = {}
    for file in files:
        return_files[file] = False
    for task in transfer.task_list(filter='status:SUCCEEDED/type:TRANSFER'):
#        print(task)
#        for event in transfer.task_event_list(task_id=task['task_id']):
#            print(event)
        for event in transfer.task_successful_transfers(task_id=task['task_id']):
            print(event)
            path = event['destination_path']
            decoded = unquote(path)
            for file in files:
                if '/' + unique_id +'/' in path and file in unquote(path):
                    return_files[file] = True
    return return_files


def check_user(email):
    auth_client = ConfidentialAppAuthClient(config.CLIENT_ID, config.GLOBUS_SECRET)
    user_info = auth_client.get_identities(usernames=email)
    identity_id = user_info.data['identities'][0]['id']
    return


def create_dir(transfer, uid, email):
    # create directory
    transfer.operation_mkdir(config.GWAS_ENDPOINT_ID, uid)
    # create shared endpoint
    shared_ep_data = {
        "DATA_TYPE": "shared_endpoint",
        "host_endpoint": config.GWAS_ENDPOINT_ID,
        "host_path": '/~/' + uid,
        "display_name": 'ebi#gwas#' + uid,
        # optionally specify additional endpoint fields
        "description": 'ebi#gwas#' + uid,
        "owner_string": "GWAS Catalog",
        "contact_email": "gwas-dev@ebi.ac.uk",
        "organization": "EBI"
    }
    create_result = transfer.create_shared_endpoint(shared_ep_data)
    endpoint_id = create_result.data['id']
    # get user info
    auth_client = ConfidentialAppAuthClient(config.CLIENT_ID, config.GLOBUS_SECRET)
    user_info = auth_client.get_identities(usernames=email)
    identity_id = user_info.data['identities'][0]['id']

    # add user to endpoint
    rule_data = {
        "DATA_TYPE": "access",
        "principal_type": "identity",
        "principal": identity_id,
        "path": '/',
        "permissions": "rw",
        "notify_email": email
    }
    transfer.add_endpoint_acl_rule(endpoint_id, rule_data)
    return endpoint_id


def load_tokens_from_db():
    """Load a set of saved tokens."""
    mongo_client = MongoClient(config.MONGO_URI) 
    globus_db = mongo_client['globus-tokens']
    globus_db_collection = globus_db['tokens']
    tokens = globus_db_collection.find_one({})
    return tokens


def save_tokens_to_db(tokens):
    """Save a set of tokens for later use."""
    mongo_client = MongoClient(config.MONGO_URI) 
    globus_db = mongo_client['globus-tokens']
    globus_db_collection = globus_db['tokens']
    resp = globus_db_collection.find_one({})
    if resp:
        globus_db_collection.replace_one({'_id': resp["_id"]}, tokens)
    else:
        globus_db_collection.insert(tokens, check_keys=False)
#    script_dir = os.path.dirname(__file__)  # <-- absolute dir the script is in
#    with open(os.path.join(script_dir, filepath), 'w') as f:
#        json.dump(tokens, f)


def update_tokens_file_on_refresh(token_response):
    """
    Callback function passed into the RefreshTokenAuthorizer.
    Will be invoked any time a new access token is fetched.
    """
    save_tokens_to_db(token_response.by_resource_server)


def do_native_app_authentication(client_id, redirect_uri,
                                 requested_scopes=None):
    """
    Does a Native App authentication flow and returns a
    dict of tokens keyed by service name.
    """
    client = NativeAppAuthClient(client_id=client_id)

    # pass refresh_tokens=True to request refresh tokens
    client.oauth2_start_flow(refresh_tokens=True)
    url = client.oauth2_get_authorize_url()
    print('Native App Authorization URL: \n{}'.format(url))

    if not is_remote_session():
        webbrowser.open(url, new=1)

    auth_code = get_input('Enter the auth code: ').strip()

    token_response = client.oauth2_exchange_code_for_tokens(auth_code)

    # return a set of tokens, organized by resource server name
    return token_response.by_resource_server


def main():
    transfer = init()


if __name__ == '__main__':
    main()
