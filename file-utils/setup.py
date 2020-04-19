from setuptools import setup

setup(
    name='atmfjstc-file-utils',
    version='1.0.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.file_utils'],

    zip_safe=True,

    description="Miscellaneous utilities for working with files in general (no specific format)",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
