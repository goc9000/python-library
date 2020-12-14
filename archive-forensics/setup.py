from setuptools import setup, find_packages

setup(
    name='atmfjstc-archive-forensics',
    version='0.4.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-iso-timestamp>=1.1.0, <2',
        'atmfjstc-binary-utils>=1.2.0, <2',
        'atmfjstc-os-forensics>=0.2.1, <2',
        'atmfjstc-py-lang-utils>=1.11.0, <2',
    ],

    zip_safe=True,

    description="Utilities for decoding archive format-specific data enums and binary structures",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: System :: Archiving",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
