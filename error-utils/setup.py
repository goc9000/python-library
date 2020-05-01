from setuptools import setup

setup(
    name='atmfjstc-error-utils',
    version='1.2.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.error_utils'],

    zip_safe=True,

    description="Utilities for working with exceptions and other failure states",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
