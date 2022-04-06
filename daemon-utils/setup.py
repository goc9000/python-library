from setuptools import setup, find_packages

setup(
    name='atmfjstc-daemon-utils',
    version='0.4.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    
    install_requires=[
    ],

    zip_safe=True,

    description="Common mechanisms used by daemons for responding to requests, handling subtasks etc.",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.9',
)
