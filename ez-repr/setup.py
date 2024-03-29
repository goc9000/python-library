from setuptools import setup, find_packages

setup(
    name='atmfjstc-ez-repr',
    version='1.1.2',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-py-lang-utils>=1.10, <2',
    ],

    zip_safe=True,

    description="Base class that provides a smarter __repr__() function for your objects",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
