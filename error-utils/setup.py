from setuptools import setup, find_packages

setup(
    name='atmfjstc-error-utils',
    version='1.3.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

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
