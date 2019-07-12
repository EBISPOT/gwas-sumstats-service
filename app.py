import simplejson
from flask import Flask, make_response, Response, jsonify
import api_endpoints as endpoints


app = Flask(__name__)
app.url_map.strict_slashes = False

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

@app.route('/studies', methods=['GET'])
def get_studies():
    resp = endpoints.studies()
    return Response(response=resp,
                    status=200,
                    mimetype="application/json")


if __name__ == '__main__':
    app.run(debug=True)
