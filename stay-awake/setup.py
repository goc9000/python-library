from setuptools import setup, find_packages

setup(
    name='atmfjstc-stay-awake',
    version='0.1.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=find_packages(where='src'),

    zip_safe=True,

    description="Prevents the system from automatically going to sleep",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: System :: Operating System",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
