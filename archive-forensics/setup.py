from setuptools import setup

setup(
    name='atmfjstc-archive-forensics',
    version='0.1.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.archive_forensics'],

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
