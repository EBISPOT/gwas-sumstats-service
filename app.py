import simplejson
from flask import Flask, make_response, Response, jsonify, request
import resources.api_endpoints as endpoints
from resources.error_classes import *


app = Flask(__name__)
app.url_map.strict_slashes = False


@app.errorhandler(APIException)
def handle_custom_api_exception(error):
    response = error.to_dict()
    response['status'] = error.status_code
    response = simplejson.dumps(response)
    resp = make_response(response, error.status_code)
    resp.mimetype = 'application/json'
    return resp

@app.errorhandler(400)
def not_found(error):
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
    return Response(response=resp,
                    status=201,
                    mimetype="application/json")



if __name__ == '__main__':
    app.run()
