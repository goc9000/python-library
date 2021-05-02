from setuptools import setup, find_packages

setup(
    name='atmfjstc-json-schema-utils',
    version='0.2.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-py-lang-utils>=1.11.3, <2',
        'jsonschema>=3, <4',
    ],

    zip_safe=True,

    description="Utilities for working with JSONSchemas",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
