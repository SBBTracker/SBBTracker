# Dependencies
1. Install [Git](https://git-scm.com/download)
2. Install [Python 3.9.9](https://www.python.org/downloads/release/python-399/)
3. (Optional) Install the Python IDE of your choice (Pycharm will help take care of most of the steps below if you use it)

# Setup
1. `git clone` this repo and cd into the directory
2. Create a virtualenv and activate it by running: 
   - `pip install virtualenv`
   - `python3 -m virtualenv ./venv/`
   - `source ./venv/Scripts/activate`
3. Set up the SBBBattleSim submodule
   - Clone the SBBBatleSim repo by running:
      - `git submodule init`
      - `git submodule update`
   - Register sbbbattlesim with pip by running:
      - `pip install -e ./sbbtracker/SBBBattleSim/`
4. Install dependencies by running:
   - `pip install -r requirements.txt`
5. Clone the assets repo from https://github.com/SBBTracker/assets and copy the `cards` folder into the SBBTracker repo.

# Run SBBTracker
1. `cd sbbtracker`
2. Run the application via `python3 application.py`
