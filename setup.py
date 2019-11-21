from setuptools import find_packages, setup

setup(
    name='gwas-sumstats-service',
    version='0.1',
    packages=find_packages(include=['sumstats_service.*','config.py']),
    entry_points={
        "console_scripts": ['validate-payload = sumstats_service.resources.validate_payload:main']
    },
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'flask',
    ],
)
