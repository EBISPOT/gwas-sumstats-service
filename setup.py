from setuptools import find_packages, setup

setup(
    name='gwas-sumstats-service',
    version='0.1',
    packages=find_packages(include=['sumstats_service']),
    data_files=[('data_files',['schema/meta_schema.yaml'])],
    entry_points={
        "console_scripts": 
            ['validate-payload = sumstats_service.resources.validate_payload:main',
             'validate-study = sumstats_service.resources.validate_study:main',
             'convert_meta = sumstats_service.resources.convert_meta:main'
            ]
    },
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'flask',
    ],
)
