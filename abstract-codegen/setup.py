from setuptools import setup

setup(
    name='atmfjstc-abstract-codegen',
    version='0.1.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.abstract_codegen'],

    install_requires=[
        'atmfjstc-ast>=1, <2',
    ],

    zip_safe=True,

    description="A model and utilities for greatly easing code generation for nearly any language",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Code Generators"
    ],
    python_requires='>=3.6',
)
