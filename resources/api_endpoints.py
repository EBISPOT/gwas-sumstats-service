import simplejson
from urllib.parse import unquote
import logging
from flask import request, url_for
from collections import OrderedDict


def root():
    response = {
        '_links': OrderedDict([
                ('studies', create_href('get_studies'))
            ])
        }
    return simplejson.dumps(response)

def studies():
    response = {}
    return simplejson.dumps(response)

def create_href(method_name, params=None):
    params = params or {}
    params['_external'] = True
    return {'href': unquote(
        url_for(method_name, **params)
    )}

