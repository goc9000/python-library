from setuptools import setup, find_packages

setup(
    name='atmfjstc-file-utils',
    version='1.3.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-error-utils>=1.1, <2',
    ],

    zip_safe=True,

    description="Miscellaneous utilities for working with files in general (no specific format)",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
