from setuptools import setup, find_packages

setup(
    name='atmfjstc-ast',
    version='1.5.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    
    install_requires=[
        'atmfjstc-py-lang-utils>=1, <2',
        'atmfjstc-xtd-type-spec>=1.1, <2',
        'atmfjstc-ez-repr>=1.1, <2'
    ],

    zip_safe=True,

    description="Base class for building Abstract Syntax Trees",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Code Generators"
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
