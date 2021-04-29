from setuptools import setup, find_packages

setup(
    name='atmfjstc-sysd-daemon',
    version='0.1.1',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    install_requires=[
        'atmfjstc-cli-utils>=1.8.0, <2',
        'pidlockfile>=0.0',
        'sdnotify>=0.3'
    ],

    zip_safe=True,

    description="Simple harness for Linux daemons running via systemd",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Topic :: System",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
