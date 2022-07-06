from setuptools import setup, find_packages

setup(
    name='atmfjstc-gz-file',
    version='1.0.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-binary-utils>=1, <2',
        'atmfjstc-file-utils>=1.2, <2',
    ],

    zip_safe=True,

    description="Advanced interface for reading multi-member GZip files with all metadata",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: System :: Archiving :: Compression",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
