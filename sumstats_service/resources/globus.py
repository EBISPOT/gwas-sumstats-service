import os
import pathlib
from datetime import date
from typing import Any, Union
from urllib.parse import unquote

from globus_sdk import (
    ClientCredentialsAuthorizer,
    ConfidentialAppAuthClient,
    DeleteData,
    GCSClient,
    GlobusAPIError,
    GuestCollectionDocument,
    TransferAPIError,
    TransferClient,
    scopes,
)

from sumstats_service import config, logger_config
import logging

try:
    logger_config.setup_logging()
    logger = logging.getLogger(__name__)
except Exception as e:
    logging.basicConfig(level=logging.DEBUG, format="(%(levelname)s): %(message)s")
    logger = logging.getLogger(__name__)
    logger.error(f"Logging setup failed: {e}")


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


def get_authorizer(scope: Any) -> ClientCredentialsAuthorizer:
    """Get a Globus client authorizer
    which can be used to authenticate the GCS and transfer clients

    Arguments:
        scope -- Globus scope

    Returns:
        ClientCredentialsAuthorizer
    """
    confidential_client = ConfidentialAppAuthClient(
        client_id=config.CLIENT_ID, client_secret=config.CLIENT_SECRET
    )
    authorizer = ClientCredentialsAuthorizer(confidential_client, scopes=scope)
    return authorizer


def init_transfer_client() -> TransferClient:
    """Initialise transfer client

    Returns:
        Globus transfer client
    """
    scope = (
        "urn:globus:auth:scope:transfer.api.globus.org:all"
        f"[*https://auth.globus.org/scopes/{config.MAPPED_COLLECTION_ID}/data_access]"
    )
    transfer_client = TransferClient(authorizer=get_authorizer(scope=scope))
    transfer_client.endpoint_autoactivate(config.MAPPED_COLLECTION_ID)
    return transfer_client


def init_gcs_client() -> GCSClient:
    """Initialise a globus connect server client

    Returns:
        GCSClient
    """
    scope = scopes.GCSEndpointScopeBuilder(config.GWAS_ENDPOINT_ID).make_mutable(
        "manage_collections"
    )
    scope.add_dependency(
        scopes.GCSCollectionScopeBuilder(config.MAPPED_COLLECTION_ID).data_access
    )
    client = GCSClient(config.GLOBUS_HOSTNAME, authorizer=get_authorizer(scope=scope))
    return client
    # scope = (
    #     "urn:globus:auth:scope:transfer.api.globus.org:all"
    #     f"[*https://auth.globus.org/scopes/{config.MAPPED_COLLECTION_ID}/data_access]"
    # )
    # transfer_client = TransferClient(authorizer=get_authorizer(scope=scope))
    # transfer_client.endpoint_autoactivate(config.MAPPED_COLLECTION_ID)
    # return transfer_client

def dir_contents(transfer, unique_id) -> Union[list, None]:
    # print out a directory listing from an endpoint
    contents = []
    try:
        for entry in transfer.operation_ls(
            config.MAPPED_COLLECTION_ID, path="/~/" + unique_id
        ):
            contents.append(entry["name"] + ("/" if entry["type"] == "dir" else ""))
    except TransferAPIError:
        return None
    return contents


def get_upload_status(transfer, unique_id, files):
    return_files = {}
    for file in files:
        return_files[file] = False
    for task in transfer.task_list(filter="status:SUCCEEDED/type:TRANSFER"):
        for event in transfer.task_successful_transfers(task_id=task["task_id"]):
            print(event)
            path = event["destination_path"]
            for file in files:
                if "/" + unique_id + "/" in path and file in unquote(path):
                    return_files[file] = True
    return return_files


def check_user(email: str) -> Union[str, None]:
    if email:
        auth_client = ConfidentialAppAuthClient(config.CLIENT_ID, config.CLIENT_SECRET)
        user_info = auth_client.get_identities(usernames=email)
        user_identity = user_info.data["identities"]
        identity_id = user_identity[0]["id"] if user_identity else None
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


def guest_collection_document(
    dirname: str, display_name: str
) -> GuestCollectionDocument:
    return GuestCollectionDocument(
        public="True",
        collection_base_path=dirname,
        display_name=display_name,
        mapped_collection_id=config.MAPPED_COLLECTION_ID,
    )


def role_data(collection_id: str, identity: str, role: str = "administrator") -> dict:
    return {
        "DATA_TYPE": "role#1.0.0",
        "collection": collection_id,
        "principal": identity,
        "role": role,
    }


def create_guest_collection(uid: str, email: str = None) -> str:
    """Create guest collection/shared endpoint

    Returns:
        guest collection/endpoint id
    """
    user_id = check_user(email)
    if user_id:
        """create shared endpoint"""
        dirname = "/~/" + uid
        display_name = "-".join([str(date.today()), uid[0:8]])
        collection_document = guest_collection_document(dirname, display_name)
        gcs_client = init_gcs_client()
        response = gcs_client.create_collection(collection_document)
        endpoint_id = response["id"]
        """ add role for administrator"""
        gcs_client.create_role(
            role_data(
                collection_id=endpoint_id,
                identity=f"urn:globus:auth:identity:{config.GWAS_IDENTITY}",
            )
        )
        """ add role for gwas group"""
        gcs_client.create_role(
            role_data(
                collection_id=endpoint_id,
                identity=f"urn:globus:groups:id:{config.GWAS_GLOBUS_GROUP}",
            )
        )
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
    transfer_client = init_transfer_client()
    rule_data = {
        "DATA_TYPE": "access",
        "principal_type": "identity",
        "principal": user_id,
        "path": "/",
        "permissions": "rw",
    }
    transfer_client.add_endpoint_acl_rule(collection_id, rule_data)


def rename_file(dest_dir, source, dest):
    transfer = init_transfer_client()
    try:
        dir_ls = transfer.operation_ls(config.MAPPED_COLLECTION_ID, path=dest_dir)
        files = [os.path.join(dest_dir, f["name"]) for f in dir_ls]
        if dest not in files:
            transfer.operation_rename(config.MAPPED_COLLECTION_ID, source, dest)
    except TransferAPIError as e:
        logger.info(e)
        return False
    return True


def list_files(directory):
    transfer = init_transfer_client()
    files = []
    try:
        dir_ls = transfer.operation_ls(config.MAPPED_COLLECTION_ID, path=directory)
        files = [os.path.join(directory, f["name"]) for f in dir_ls]
    except TransferAPIError as e:
        logger.info(e)
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
    logger.info(f">> remove_endpoint_and_all_contents {uid=}")
    transfer = init_transfer_client()
    deactivate_status = False
    endpoint_id = get_endpoint_id_from_uid(uid, transfer_client=transfer)
    logger.info(f">> remove_endpoint_and_all_contents {uid=} :: {endpoint_id=}")
    if endpoint_id:
        logger.info(f">> remove_endpoint_and_all_contents {uid=} :: {endpoint_id=} true")
        if remove_path(path_to_remove=uid, transfer_client=transfer):
            logger.info(f">> remove_endpoint_and_all_contents {uid=} :: remove_path true")
            deactivate_status = deactivate_endpoint(endpoint_id)
            logger.info(f">> remove_endpoint_and_all_contents {uid=} :: {deactivate_status=}")

    return deactivate_status


def deactivate_endpoint(endpoint_id, gcs_client=None):
    logger.info(f">> deactivate_endpoint {endpoint_id=}")
    gcs = gcs_client if gcs_client else init_gcs_client()
    status = gcs.delete_collection(endpoint_id)
    logger.info(f">> deactivate_endpoint {endpoint_id=} :: {status=}")
    return status.http_status


def get_endpoint_id_from_uid(uid: str, transfer_client: TransferClient = None) -> Union[str, None]:
    transfer = transfer_client if transfer_client else init_transfer_client()
    search_pattern = f"-{uid[0:8]}"
    endpoint_id = None
    results = transfer.endpoint_search(search_pattern, filter_scope="shared-by-me")
    if results.get("DATA"):
        endpoint_id = results.get("DATA")[0].get("id")
    return endpoint_id


def main():
    transfer = init_transfer_client()


if __name__ == "__main__":
    main()
