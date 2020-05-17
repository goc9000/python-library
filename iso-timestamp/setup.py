from setuptools import setup

setup(
    name='atmfjstc-iso-timestamp',
    version='1.1.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.iso_timestamp'],

    zip_safe=True,

    description="Utilities for working with ISO format text timestamps",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
