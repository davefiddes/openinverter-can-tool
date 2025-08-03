# How to contribute to OpenInverter CAN Tool

## **Did you find a bug?**

* **Ensure the bug was not already reported** by searching on GitHub under [Issues](https://github.com/davefiddes/openinverter-can-tool/issues).

* If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/davefiddes/openinverter-can-tool/issues/new). Be sure to include a **title and clear description**, as much relevant information as possible, and a **shell or command prompt log** demonstrating the problematic behavior.

## **Do you have questions or comments about the tool?**

* If you are not sure how to use the tool or have questions about its suitability for your project(s) then please join in on the [OpenInverter forum topic](https://openinverter.org/forum/viewtopic.php?t=2907).

## **Did you write a patch that fixes a bug?**

* Open a new GitHub pull request with the patch.

* Ensure the PR description clearly describes the problem and solution. Include the relevant issue number if applicable.

* Where possible include a set of unit tests that exercise the new functionality. The exception to this is changes to the `cli.py` main program which are harder to unit test.

* Ensure that code conforms to the PEP8 conventions using the `flake8` code linter.

* Wait until the GitHub PR checks are green before submitting.

* Thank you!

## **Would you like to set up a development environment for the tool?**

If you want to be able to change the code while using it, clone it then install
it in development mode:

```text
    git clone https://github.com/davefiddes/openinverter_can_tool.git
    cd openinverter_can_tool
    python -m venv venv
    . venv/bin/activate
    pip install -e .[dev,test]
    pre-commit install
```

To exit the virtualenv environment run `dectivate`. To resume development operation the virtualenv can be restarted by running:

```text
    . venv/bin/activate
```

It is possible to run unit tests and check python code linting on all supported python versions by running the `tox` command.
