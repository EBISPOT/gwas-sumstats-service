import requests
import logging

from requests.adapters import HTTPAdapter, Retry


logging.basicConfig(level=logging.ERROR, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


def download_with_requests(url, params=None, headers=None):
    """
    Return content from URL if status code is 200
    :param url: 
    :param headers: 
    :return: content in bytes or None
    """
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount(url, HTTPAdapter(max_retries=retries))
    try:
        r = s.get(url, params=params, headers=headers)
        status_code = r.status_code
        if status_code == 200:
            return r.content
        else:
            logger.warning(f"{url} returned {status_code} status code")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(e)
        return None