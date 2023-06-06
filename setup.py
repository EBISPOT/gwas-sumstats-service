from setuptools import find_packages, setup

setup(
    name='gwas-sumstats-service',
    version='v1.3.6',
    packages=find_packages(include=['sumstats_service']),
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
    ]
)
