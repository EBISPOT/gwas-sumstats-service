import simplejson
import config
import json
from flask import Flask, make_response, Response, jsonify, request
import sumstats_service.resources.api_endpoints as endpoints
import sumstats_service.resources.api_utils as au
from sumstats_service.resources.error_classes import *
from celery import Celery


app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = '{0}://{1}:{2}/0'.format(config.BROKER, config.BROKER_HOST, config.BROKER_PORT)
app.config['CELERY_RESULT_BACKEND'] =  '{0}://{1}:{2}/0'.format(config.BROKER, config.BROKER_HOST, config.BROKER_PORT)
app.url_map.strict_slashes = False

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@app.errorhandler(APIException)
def handle_custom_api_exception(error):
    response = error.to_dict()
    response['status'] = error.status_code
    response = simplejson.dumps(response)
    resp = make_response(response, error.status_code)
    resp.mimetype = 'application/json'
    return resp


@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@app.errorhandler(500)
def internal_server_error(error):
    return make_response(jsonify({'message': 'Internal Server Error.', 'status': 500, 'error': 'Internal Server Error'})
, 500)


@app.route('/')
def root():
    resp = endpoints.root()
    return Response(response=resp,
                    status=200,
                    mimetype="application/json")


@app.route('/sum-stats', methods=['POST'])
def sumstats():
    content = request.get_json(force=True)
    resp = endpoints.create_studies(content)
    if resp:
        callback_id =json.loads(resp)['callbackID']
        run_background_task(au.validate_files_from_payload, callback_id)
    return Response(response=resp,
                    status=201,
                    mimetype="application/json")

@celery.task
def run_background_task(task, *args):
    task(*args)

@app.route('/sum-stats/<string:callback_id>')
def get_sumstats(callback_id):
    resp = endpoints.get_sumstats(callback_id=callback_id)
    return Response(response=resp,
                    status=200,
                    mimetype="application/json")



if __name__ == '__main__':
    app.run()