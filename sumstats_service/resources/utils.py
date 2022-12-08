import requests
import logging

logging.basicConfig(level=logging.ERROR, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


def download_with_requests(url, params=None, headers=None):
    """
    Return content from URL if status code is 200
    :param url: 
    :param headers: 
    :return: content in bytes or None
    """
    try:
        with requests.get(url, params=params, headers=headers) as r:
            status_code = r.status_code
            if status_code != 200:
                logger.error(f"{url} returned {status_code} status code")
                return None
            else:
                return r.content
    except requests.exceptions.RequestException as e:
        logger.error(e)
        return None