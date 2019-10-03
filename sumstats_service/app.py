import simplejson
import config
import json
from flask import Flask, make_response, Response, jsonify, request
import sumstats_service.resources.api_endpoints as endpoints
import sumstats_service.resources.api_utils as au
from sumstats_service.resources.error_classes import *
from celery import Celery
import os


app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = '{msg_protocol}://{user}:{pwd}@{host}:{port}'.format(
        msg_protocol=os.environ['CELERY_PROTOCOL'], 
        user=os.environ['CELERY_USER'],
        pwd=os.environ['CELERY_PASSWORD'],
        host=os.environ['QUEUE_HOST'],
        port=os.environ['QUEUE_PORT']
        )
app.config['CELERY_RESULT_BACKEND'] = 'rpc://' #'{0}://guest@{1}:{2}'.format(config.BROKER, config.BROKER_HOST, config.BROKER_PORT)
app.url_map.strict_slashes = False

celery = Celery('app', broker=app.config['CELERY_BROKER_URL'], backend=app.config['CELERY_RESULT_BACKEND'])
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


@app.route('/v1/sum-stats', methods=['POST'])
def sumstats():
    content = request.get_json(force=True)
    print(content)
    resp = endpoints.create_studies(content)
    if resp:
        callback_id = json.loads(resp)['callbackID']
        validate_files_in_background.apply_async(args=[callback_id, content])
    return Response(response=resp,
                    status=201,
                    mimetype="application/json")


@app.route('/v1/sum-stats/<string:callback_id>', methods=['GET'])
def get_sumstats(callback_id):
    resp = endpoints.get_sumstats(callback_id=callback_id)
    return Response(response=resp,
                    status=200,
                    mimetype="application/json")


@app.route('/v1/sum-stats/<string:callback_id>', methods=['DELETE'])
def delete_sumstats(callback_id):
    resp = endpoints.delete_sumstats(callback_id=callback_id)
    if resp:
        remove_payload_files.apply_async(args=[callback_id])
    return Response(response=resp,
                    status=200,
                    mimetype="application/json")


# Celery tasks

@celery.task(queue='preval', options={'queue': 'preval'})
def validate_files_in_background(callback_id, content):
    results = au.validate_files_from_payload(callback_id, content)
    store_validation_results.apply_async(args=[results])


@celery.task(queue='postval', options={'queue': 'postval'})
def store_validation_results(results):
    au.store_validation_results_in_db(results)


@celery.task(queue='preval', options={'queue': 'preval'})
def remove_payload_files(callback_id):
    au.remove_payload_files(callback_id)


if __name__ == '__main__':
    app.run()
