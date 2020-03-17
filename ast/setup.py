from setuptools import setup

setup(
    name='atmfjstc-ast',
    version='1.0.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.ast'],
    
    install_requires=[
        'atmfjstc-py-lang-utils>=1, <2',
        'atmfjstc-xtd-type-spec>=1, <2',
    ],

    zip_safe=True,

    description="Base class for building Abstract Syntax Trees",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Code Generators"
    ],
    python_requires='>=3.6',
)
