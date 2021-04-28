from setuptools import setup, find_packages

setup(
    name='atmfjstc-osx-daemon',
    version='0.3.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-cli-utils>=1.8.0, <2',
        'pidlockfile>=0.0'
    ],

    zip_safe=True,

    description="Simple harness for daemons running on OS X",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Topic :: System",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
