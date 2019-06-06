# Unit Test Builder POC

This is a POC that allows running EDK2 host based unit tests on Windows 10.  Eventually this capability will be moved into the mu_build system.  

## Temporary Requirement

Currently the gitdependnecy ext dep is not in the released pip module and the cmocka pkg uses this.  

Follow normal pip_requirments.txt process except afterwords go override the the mu_environment pip module.  It needs to be installed from source.  This can be done easily by cloning the git repo and pip installing the local resource.  

``` cmd
git clone https://github.com/microsoft/mu_pip_environment.git
git checkout origin/personal/sebrogan/pip_git_dependencies
```

Then in your virutal environmant install this as your mu_environment.  Must run the command from the root of the mu_environment repo. 

``` cmd
pip install -e .
```

## Running the tests

Run **UnitTestBuild.py** from the command window.  