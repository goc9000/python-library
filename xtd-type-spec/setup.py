from setuptools import setup, find_packages

setup(
    name='atmfjstc-xtd-type-spec',
    version='1.1.2',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-py-lang-utils>=1, <2',
    ],

    zip_safe=True,

    description="An extended type specification and improved isinstance/issubclass variants to go with it",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
