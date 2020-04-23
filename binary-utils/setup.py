from setuptools import setup

setup(
    name='atmfjstc-binary-utils',
    version='0.2.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.binary_utils'],

    zip_safe=True,

    description="Utilities for parsing binary and bit-level data",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
