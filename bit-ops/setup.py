from setuptools import setup

setup(
    name='atmfjstc-bit-ops',
    version='0.1.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.bit_ops'],

    zip_safe=True,

    description="Advanced bit manipulation utilities",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
