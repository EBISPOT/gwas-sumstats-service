import os
from typing import Any, Union
from datetime import date
import webbrowser
from urllib.parse import unquote
import pathlib
from sumstats_service import config
import globus_sdk
from globus_sdk import (NativeAppAuthClient, TransferClient, AccessTokenAuthorizer, RefreshTokenAuthorizer,
                        ClientCredentialsAuthorizer, ConfidentialAppAuthClient, DeleteData,
                        GCSClient, scopes, GuestCollectionDocument, TransferAPIError, GlobusAPIError)
from sumstats_service.resources.globus_utils import is_remote_session
from pymongo import MongoClient


get_input = getattr(__builtins__, 'raw_input', input)
# uncomment the next line to enable debug logging for network requests
#enable_requests_logging()


def mkdir(unique_id: str, email_address: str = None) -> str:
    """Create a globus guest collection on a specific
    directory and return collection id 

    Arguments:
        unique_id -- name for directory

    Keyword Arguments:
        email_address -- globus account (default: {None})

    Returns:
        globus collection id
    """
    transfer_client = init_transfer_client()
    create_dir(transfer_client, dirname=unique_id)
    endpoint_id = create_guest_collection(unique_id, email_address)
    return endpoint_id


def list_dir(unique_id):
    transfer = init_transfer_client()
    return dir_contents(transfer, unique_id)


def init_transfer_client() -> TransferClient:
    """Initialise transfer client

    Returns:
        Globus transfer client
    """
    # if we already have tokens, load and use them
    tokens = load_tokens_from_db()
    if not tokens:
        # if we need to get tokens, start the Native App authentication process
        tokens = do_native_app_authentication(config.TRANSFER_CLIENT_ID, config.REDIRECT_URI, config.SCOPES)
        save_tokens_to_db(tokens)
    transfer_tokens = tokens.get('transfer.api.globus.org')
    native_app_client = NativeAppAuthClient(client_id=config.TRANSFER_CLIENT_ID)
    authorizer = RefreshTokenAuthorizer(transfer_tokens['refresh_token'],
                                        native_app_client,
                                        access_token=transfer_tokens['access_token'],
                                        expires_at=transfer_tokens['expires_at_seconds'],
                                        on_refresh=save_tokens_to_db(tokens))
    transfer_client = TransferClient(authorizer=authorizer)
    transfer_client.endpoint_autoactivate(config.MAPPED_COLLECTION_ID)
    return transfer_client


def init_gcs_client() -> GCSClient:
    """Initialise a globus connect server client

    Returns:
        GCSClient
    """
    scope = scopes.GCSEndpointScopeBuilder(config.GWAS_ENDPOINT_ID).make_mutable("manage_collections")
    scope.add_dependency(scopes.GCSCollectionScopeBuilder(config.MAPPED_COLLECTION_ID).data_access)
    confidential_client = globus_sdk.ConfidentialAppAuthClient(
        client_id=config.CLIENT_ID, client_secret=config.CLIENT_SECRET
    )
    authorizer = globus_sdk.ClientCredentialsAuthorizer(confidential_client, scopes=scope)
    client = GCSClient(config.GLOBUS_HOSTNAME, authorizer=authorizer)
    return client


def dir_contents(transfer, unique_id) -> Union[list, None]:
    # print out a directory listing from an endpoint
    contents = []
    try:
        for entry in transfer.operation_ls(config.MAPPED_COLLECTION_ID, path='/~/' + unique_id):
            contents.append(entry['name'] + ('/' if entry['type'] == 'dir' else ''))
    except TransferAPIError:
        return None  
    return contents


def get_upload_status(transfer, unique_id, files):
    return_files = {}
    for file in files:
        return_files[file] = False
    for task in transfer.task_list(filter='status:SUCCEEDED/type:TRANSFER'):
        for event in transfer.task_successful_transfers(task_id=task['task_id']):
            print(event)
            path = event['destination_path']
            for file in files:
                if '/' + unique_id + '/' in path and file in unquote(path):
                    return_files[file] = True
    return return_files


def check_user(email: str) -> Union[str, None]:
    if email:
        auth_client = ConfidentialAppAuthClient(config.CLIENT_ID, config.CLIENT_SECRET)
        user_info = auth_client.get_identities(usernames=email)
        user_identity = user_info.data['identities']
        identity_id = user_identity[0]['id'] if user_identity else None
        return identity_id
    return None


def create_dir(transfer_client: TransferClient, dirname: str) -> None:
    """Create a globus direct

    Arguments:
        transfer_client -- transfer client
        dirname -- directory path

    Returns:
        None
    """
    try:
        transfer_client.operation_mkdir(config.MAPPED_COLLECTION_ID, dirname)
    except GlobusAPIError as error:
        print(error)


def guest_collection_document(dirname: str, display_name: str) -> GuestCollectionDocument:
    return GuestCollectionDocument(
        public="True",
        collection_base_path=dirname,
        display_name=display_name,
        mapped_collection_id=config.MAPPED_COLLECTION_ID
        )


def role_data(collection_id: str, identity: str, role: str = 'administrator') -> dict:
    return {"DATA_TYPE": "role#1.0.0",
            "collection": collection_id,
            "principal": identity,
            "role": role
            }


def create_guest_collection(uid: str, email: str = None) -> str:
    """Create guest collection/shared endpoint

    Returns:
        guest collection/endpoint id
    """
    user_id = check_user(email)
    if user_id:
        """ create shared endpoint"""
        dirname = '/~/' + uid
        display_name = '-'.join([str(date.today()), uid[0:8]])
        collection_document = guest_collection_document(dirname, display_name)
        gcs_client = init_gcs_client()
        response = gcs_client.create_collection(collection_document)
        endpoint_id = response['id']
        """ add role for administrator"""
        gcs_client.create_role(role_data(collection_id=endpoint_id,
                                         identity=f"urn:globus:auth:identity:{config.GWAS_IDENTITY}"
                                         ))
        """ add role for gwas group"""
        gcs_client.create_role(role_data(collection_id=endpoint_id,
                                         identity=f"urn:globus:groups:id:{config.GWAS_GLOBUS_GROUP}"
                                         ))
        """ add user to endpoint"""
        add_permissions_to_endpoint(collection_id=endpoint_id, user_id=user_id)
        return endpoint_id
    else:
        return None


def add_permissions_to_endpoint(collection_id: str, user_id: str) -> None:
    """Add ACL to guest collection
    
    Requires a transfer client call

    Arguments:
        collection_id -- collection id
        user_id -- user identity
    """
    scopes = "urn:globus:auth:scope:transfer.api.globus.org:all"
    authorizer = ClientCredentialsAuthorizer(
        ConfidentialAppAuthClient(config.CLIENT_ID, config.CLIENT_SECRET),
        scopes
        )
    transfer_client = TransferClient(authorizer=authorizer)
    rule_data = {
        "DATA_TYPE": "access",
        "principal_type": "identity",
        "principal": user_id,
        "path": "/",
        "permissions": "rw",
    }
    transfer_client.add_endpoint_acl_rule(collection_id, rule_data)


def load_tokens_from_db() -> Union[Any, None]:
    """Load a set of saved tokens."""
    mongo_client = MongoClient(config.MONGO_URI, username=config.MONGO_USER, password=config.MONGO_PASSWORD)
    globus_db = mongo_client[config.MONGO_DB]
    globus_db_collection = globus_db['globus-tokens']
    tokens = globus_db_collection.find_one({}, {'_id': 0})
    return tokens


def load_requirements_data_from_db():
    """Load requirements data."""
    mongo_client = MongoClient(config.MONGO_URI, username=config.MONGO_USER, password=config.MONGO_PASSWORD)
    globus_db = mongo_client[config.MONGO_DB]
    globus_db_collection = globus_db['globus-requirements']
    requirements_data = globus_db_collection.find_one({}, {'_id': 0})
    return requirements_data


def save_tokens_to_db(tokens) -> None:
    """Save a set of tokens for later use."""
    mongo_client = MongoClient(config.MONGO_URI, username=config.MONGO_USER, password=config.MONGO_PASSWORD)
    globus_db = mongo_client[config.MONGO_DB]
    globus_db_collection = globus_db['globus-tokens']
    resp = globus_db_collection.find_one({})
    if resp:
        globus_db_collection.replace_one({'_id': resp["_id"]}, tokens)
    else:
        globus_db_collection.insert(tokens, check_keys=False)


def save_requirements_to_db(requirements):
    mongo_client = MongoClient(config.MONGO_URI, username=config.MONGO_USER, password=config.MONGO_PASSWORD)
    globus_db = mongo_client[config.MONGO_DB] # 'globus-tokens'
    globus_db_collection = globus_db['globus-requirements']
    resp = globus_db_collection.find_one({})
    if resp:
        globus_db_collection.replace_one({'_id': resp["_id"]}, requirements)
    else:
        globus_db_collection.insert(requirements, check_keys=False)


def do_native_app_authentication(client_id, redirect_uri=None,
                                 requested_scopes=None) -> dict:
    """
    Does a Native App authentication flow and returns a
    dict of tokens keyed by service name.
    """
    client = NativeAppAuthClient(client_id=client_id)
    # pass refresh_tokens=True to request refresh tokens
    client.oauth2_start_flow(refresh_tokens=True, requested_scopes=requested_scopes)
    url = client.oauth2_get_authorize_url()
    print('Native App Authorization URL: \n{}'.format(url))
    if not is_remote_session():
        webbrowser.open(url, new=1)
    auth_code = get_input('Enter the auth code: ').strip()
    token_response = client.oauth2_exchange_code_for_tokens(auth_code)
    # return a set of tokens, organized by resource server name
    return token_response.by_resource_server


def rename_file(dest_dir, source, dest):
    transfer = init_transfer_client()
    try:
        dir_ls = transfer.operation_ls(config.MAPPED_COLLECTION_ID,D, path=dest_dir)
        files = [os.path.join(dest_dir, f["name"]) for f in dir_ls]
        if dest not in files:
            transfer.operation_rename(config.MAPPED_COLLECTION_ID, source, dest)
    except TransferAPIError as e:
        print(e)
        return False
    return True

def list_files(directory):
    transfer = init_transfer_client()
    files = []
    try:
        dir_ls = transfer.operation_ls(config.MAPPED_COLLECTION_ID, path=directory)
        files = [os.path.join(directory, f["name"]) for f in dir_ls]
    except TransferAPIError as e:
        print(e)
    return files

def filepath_exists(path):
    pardir = pathlib.Path(path).parent
    filename = pathlib.Path(path).name
    if filename in list_files(pardir):
        return True
    return False


def remove_path(path_to_remove, transfer_client=None):
    transfer = transfer_client if transfer_client else init_transfer_client()
    ddata = DeleteData(transfer, config.MAPPED_COLLECTION_ID, recursive=True)
    ddata.add_item(path_to_remove)
    delete_result = transfer.submit_delete(ddata)
    return delete_result


def remove_endpoint_and_all_contents(uid):
    transfer = init_transfer_client()
    deactivate_status = False
    endpoint_id = get_endpoint_id_from_uid(uid, transfer_client=transfer)
    if endpoint_id:
        if remove_path(path_to_remove=uid, transfer_client=transfer):
            deactivate_status = deactivate_endpoint(endpoint_id, transfer_client=transfer)
    return deactivate_status


def deactivate_endpoint(endpoint_id, transfer_client=None):
    transfer = transfer_client if transfer_client else init_transfer_client()
    status = transfer.delete_endpoint(endpoint_id)
    return status.http_status


def get_endpoint_id_from_uid(uid, transfer_client=None):
    transfer = transfer_client if transfer_client else init_transfer_client()
    search_pattern = uid[0:8]
    host_path = "/~/{}/".format(uid)
    endpoint_id = None
    for ep in transfer.endpoint_search(search_pattern, filter_scope='shared-by-me'):
        if ep['host_path'] == host_path:
            endpoint_id = ep['id']
    return endpoint_id


def main():
    transfer = init_transfer_client()


if __name__ == '__main__':
    main()
