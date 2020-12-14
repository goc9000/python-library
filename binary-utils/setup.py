from setuptools import setup, find_packages

setup(
    name='atmfjstc-binary-utils',
    version='1.2.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-file-utils>=1.2, <2',
    ],

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
