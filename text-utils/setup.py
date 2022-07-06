from setuptools import setup, find_packages

setup(
    name='atmfjstc-text-utils',
    version='1.5.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

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
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
