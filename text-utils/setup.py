from setuptools import setup

setup(
    name='atmfjstc-text-utils',
    version='1.2.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.text_utils'],

    install_requires=[
        'atmfjstc-py-lang-utils>=1, <2',
    ],

    zip_safe=True,

    description="Miscellaneous utilities for processing plain text",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Text Processing",
    ],
    python_requires='>=3.6',
)
