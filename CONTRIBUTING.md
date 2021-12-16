# Setup
1. Install [Git](https://git-scm.com/download)
2. Install [Python 3.9.9](https://www.python.org/downloads/release/python-399/)
3. (Optional) Install the Python IDE of your choice (Pycharm will help take care of most of the steps below if you use it)
4. `git clone` this repo and cd into the directory
5. Install virtualenv by running:
   `pip install virtualenv`
6. Create a virtualenv:
   `python3 -m virtualenv ./venv/`
   and you activate the virtualenv by running:
   `source ./venv/Scripts/activate`
7. Install dependencies by running:
   `pip install -r requirements.txt`
8. Clone the assets repo from https://github.com/SBBTracker/assets and copy the `cards` folder into the SBBTracker repo.
9. `cd src`
10. Run the application via `python3 application.py`
