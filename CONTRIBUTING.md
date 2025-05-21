Contributing
===============

## Reporting Issues

Please use the issues tracker to report any issues along with any additional information (such as the asset that failed).

Bug patches should be reviewed by at least one other person before the update will be released to PROD.
The commit should reference the issue number that it is fixing.

All raised bugs should be added to the unit testing so that they will not occur again in the future.

## Feature Requests

Want a new asset type to be supported or want additional asset information?
Raise an issue on the issue tracker and give it the label ``enhancement``.

## Pull Requests

If you want to submit a code change, git clone the ``master`` branch to get the latest version of the code.
If you do not have collaborator permissions to the repo you will need to create your own local fork of the project first.

Then create a new feature branch and commit your changes.
Once finished, you should then create a pull request to merge your changes back into the ``master`` branch.

## Releases

When a new version is to be released to PowerFactory PROD, the ``master`` branch will be merged into ``release`` branch and the version number increased with [Semantic Versioning](http://semver.org/). This will occur only if all unit tests are passing.

## Maintainers
* **Primary:**   dan.park@energyq.com.au
* **Secondary:**  ?