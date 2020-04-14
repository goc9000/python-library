from setuptools import setup

setup(
    name='atmfjstc-py-lang-utils',
    version='1.5.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.py_lang_utils'],

    zip_safe=True,

    description="Atom of Justice's collection of Python language idioms and helpers for any application",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
