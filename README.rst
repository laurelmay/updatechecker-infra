``updatechecker`` Infrastructure
==================================

Deploys `updatechecker`_ to AWS using Chalice and the CDK to provide an API
and to send notifications when new versions are released. Version data is
stored in DynamoDB and notifications are sent on changes to the latest
version of any supported software.

.. _updatechecker: https://github.com/kylelaker/updatechecker

Deploying
---------

To deploy the application ensure that the AWS CDK and Chalice are installed.
This can be done with something like:

.. code-block:: shell

   $ npm install -g aws-cdk
   $ pip install -U chalice

Since the ``updatechecker`` package is only available as a source archive (not a
source or binary distribution), it has to be vendored. The vendor directory is
ignored by ``git`` but can be loaded by running ``./fetch_vendor.sh``.

The following environment variables may need to be set in order to resolve packaging
errors:

.. code-block:: shell

   $ export MULTIDICT_NO_EXTENSIONS=1
   $ export YARL_NO_EXTENSIONS=1
   $ export FROZENLIST_NO_EXTENSION=1
   $ export AIOHTTP_NO_EXTENSIONS=1
   $ export WRAPT_INSTALL_EXTENSIONS=false

Then, within the ``infrastructure`` directory run ``cdk bootstrap && cdk deploy``.

The API
-------

The API will be available at the URL in the output of the ``cdk deploy`` command. The
key is ``updatecheckerv2.EndpointURL``.

Two routes are currently provided. ``/software`` provides a list of the IDs of all
supported software. ``/software/{name}/{version}`` where ``{version}`` is usually
``latest`` and ``{name}`` is one of the IDs will provide information about that
version of the software, including the download URL, SHA1 hash, and the version
string.


Notifications
-------------

An SNS topic is created during the deployment. Subscribing to the topic will result in
a notification each time the ``latest`` version of an application is created or
updated. The format is intended for plain text email; it is not intended to be
machine readable.
