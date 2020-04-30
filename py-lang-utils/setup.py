from setuptools import setup

setup(
    name='atmfjstc-py-lang-utils',
    version='1.10.0',

    author_email='atmfjstc@protonmail.com',

    package_dir={'': 'src'},
    packages=['atmfjstc.lib.py_lang_utils'],

    # Note to self: think twice before adding any install_requires here! This is intended to be a fundamental package.

    zip_safe=True,

    description="Atom of Justice's collection of Python language idioms and helpers for any application",

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Typing :: Typed",
    ],
    python_requires='>=3.7',
)
