"""
Setup file for Streamlit Cloud
"""

from setuptools import setup, find_packages

setup(
    name="ristorapp",
    version="2.0",
    packages=find_packages(),
    install_requires=[
        "streamlit",
        "pandas",
        "pillow",
        "qrcode[pil]",
        "streamlit-autorefresh",
        "requests",
        "python-dateutil",
    ],
)