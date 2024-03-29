from setuptools import setup, find_packages

setup(
    name='atmfjstc-os-forensics',
    version='0.2.3',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-iso-timestamp>=1.0.0, <2',
        'atmfjstc-binary-utils>=1.2.0, <2',
    ],

    zip_safe=True,

    description="Utilities for decoding OS and filesystem-specific data enums and binary structures",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: System :: Filesystems",
        "Topic :: System :: Operating System",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
