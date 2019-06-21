from setuptools import setup

setup(
    name='user_creation',
    version='1.0',
    description='Creates users for Snake River School District. Also can delete old users and create accounts' +
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
