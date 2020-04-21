from setuptools import setup

setup(
    name='atmfjstc-cli-utils',
    version='1.3.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.cli_utils'],
    
    install_requires=[
        'termcolor>=1, <2',
        'atmfjstc-text-utils>=1.3, <2',
        'atmfjstc-error-utils>=1, <2',
    ],

    zip_safe=True,

    description="Utilities for command-line programs",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
