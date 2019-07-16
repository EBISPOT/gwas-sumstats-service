# gwas-sumstats-service
## GWAS summary statistics service app

This handles the uploaded summary statistics files, validates them, reports errors to the deposition app and puts valid files in the queue for sumstats file harmonisation and HDF5 loading.

## Installation

- Clone the repository
  - `git clone https://github.com/EBISPOT/gwas-sumstats-service.git`
  - `cd gwas-sumstats-service`
- Set up environment
  - `virtualenv --python=python3.6 .env`
  - `source activate .env`
  - `pip install -r requirements.txt`

## Run the tests

- `./run_tests.sh`

## Run the app

- Start the flask app on http://localhost:5000
  - `python app.py`
