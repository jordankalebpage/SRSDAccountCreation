from setuptools import setup

setup(
    name='user_creation',
    version='1.0',
    description='Creates a user for Snake River School District, as well as deleting old users and creating accounts' +
    ' for upcoming 2nd graders',
    author='Jordan Page',
    author_email='jpage628@gmail.com',
    license='MIT',
    install_requires=[
        'requests',
        'profanityfilter',
        'ldap3',
        'pysftp'
    ],
    zip_safe=False
)
