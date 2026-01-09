import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from requests.adapters import HTTPAdapter, Retry

import sumstats_service.config as config

logging.basicConfig(level=logging.ERROR, format="(%(levelname)s): %(message)s")
logger = logging.getLogger(__name__)


def download_with_requests(url, params=None, headers=None):
    """
    Return content from URL if status code is 200
    :param url:
    :param headers:
    :return: content in bytes or None
    """
    s = requests.Session()
    retries = Retry(
        total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504]
    )
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


def send_mail(
    subject: str,
    message: str,
    server: str = config.MAIL_SERVER,
    port: str = config.MAIL_PORT,
    mail_from: str = config.MAIL_FROM,
    mail_to: str = config.MAIL_TO,
) -> None:
    """Send an email

    Arguments:
        subject -- Mail subject
        message -- Message

    Keyword Arguments:
        server -- (default: {"outgoing.ebi.ac.uk"})
        port -- (default: {"587"})
        mail_from -- (default: {"gwas-dev@ebi.ac.uk"})
        mail_to -- (default: {"gwas-dev@ebi.ac.uk"})
    """

    msg = MIMEMultipart()
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    with smtplib.SMTP(server, port) as server:
        server.send_message(msg)
