from setuptools import setup, find_packages

setup(
    name='atmfjstc-iso-timestamp',
    version='1.1.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

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
