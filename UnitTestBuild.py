##
## Script to Host based unit tests
##
##
## Copyright Microsoft Corporation, 2015
##

import os
import sys
import logging
import glob
from datetime import datetime
from datetime import date
import time
import subprocess

from MuPythonLibrary.UtilityFunctions import RunCmd
from MuPythonLibrary.UtilityFunctions import RunPythonScript

from MuEnvironment.UefiBuild import UefiBuilder
from MuEnvironment import SelfDescribingEnvironment
from MuEnvironment import ShellEnvironment
from MuEnvironment import MuLogging
from MuEnvironment import PluginManager
from MuEnvironment import ConfMgmt

import xml.etree.ElementTree

#
#==========================================================================
# PLATFORM BUILD ENVIRONMENT CONFIGURATION
#
SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_PATH = SCRIPT_PATH
REQUIRED_REPOS = ('mu_basecore', 'edk2-test', 'RustPkg/External/r-efi')
PROJECT_SCOPE = ('unittest',)

MODULE_PKGS = ('mu_basecore', 'edk2-test')
MODULE_PKG_PATHS = ";".join(os.path.join(WORKSPACE_PATH, pkg_name) for pkg_name in MODULE_PKGS)

#
#==========================================================================
#

#--------------------------------------------------------------------------------------------------------
# Subclass the UEFI builder and add platform specific functionality.
#
class PlatformBuilder(UefiBuilder):

    def __init__(self, WorkSpace, PackagesPath, PInManager, PInHelper, args):
        super(PlatformBuilder, self).__init__(WorkSpace, PackagesPath, PInManager, PInHelper, args)

    def SetPlatformEnv(self):
        logging.debug("PlatformBuilder SetPlatformEnv")

        self.env.SetValue("ACTIVE_PLATFORM", "MdeModulePkg/MdeModulePkgUnitTest.dsc", "Platform Hardcoded")
        self.env.SetValue("PRODUCT_NAME", "UnitTests", "Platform Hardcoded")

        # self.env.SetValue("TARGET_ARCH", "IA32 X64", "Platform Hardcoded")
        self.env.SetValue("TARGET_ARCH", "X64", "Platform Hardcoded")
        return 0


    def SetPlatformEnvAfterTarget(self):
        logging.debug("PlatformBuilder SetPlatformEnvAfterTarget")
        #Todo add code for ia32 paths
        Tag = self.env.GetValue("TOOL_CHAIN_TAG")
        if (Tag is not None) and (Tag.upper().startswith("VSLATEST")):
            vcpath = os.environ.get("VS150INSTALLPATH", None)
            if(vcpath is None):
                logging.error("Can't launch vcvars without Install Path")
                return 0
            logging.debug("vcpath is: " + vcpath)
            interesting_keys = ["ExtensionSdkDir", "INCLUDE", "LIB"]
            interesting_keys.extend(["LIBPATH", "Path", "UniversalCRTSdkDir", "UCRTVersion", "WindowsLibPath", "WindowsSdkBinPath"])
            interesting_keys.extend(["WindowsSdkDir", "WindowsSdkVerBinPath", "WindowsSDKVersion","VCToolsInstallDir"])
            dictofvars = self.__Query_Vcvarsall(vcpath, interesting_keys, "amd64")
            for (k,v) in dictofvars.items():
                os.environ[k] = v
                logging.debug("Set {0} = {1}".format(k,v))
            
            # now get vc version
            fullPath = os.path.join(os.environ.get("VS150INSTALLPATH"), "VC", "Tools", "MSVC", os.environ.get("VS150TOOLVER"))
            #env.set_shell_var("VS2017_PREFIX", fullPath)
            logging.debug("VS2017_PREFIX is: " + fullPath)
            

        rc = 0
        return rc



    def PlatformPostBuild(self):
        rc = 0
        os.environ["CMOCKA_MESSAGE_OUTPUT"] = self.env.GetValue("TEST_OUTPUT_FORMAT", "xml")
        logging.log(MuLogging.get_section_level(), "Run Host based Unit Tests")
        path = self.env.GetValue("BUILD_OUTPUT_BASE")
        for arch in self.env.GetValue("TARGET_ARCH").split():
            logging.log( MuLogging.get_subsection_level(), "Testing for architecture: " + arch)
            cp = os.path.join(path, arch)
            for old_result in glob.iglob(os.path.join(cp, "*.result.xml")):
                os.remove(old_result)
            testList = glob.glob(os.path.join(cp, "*Test*.exe"))
            for test in testList:
                os.environ["CMOCKA_XML_FILE"] = test + ".%g." + arch + ".result.xml"
                ret = RunCmd('"' + test + '"', "", workingdir=cp)
                if(ret != 0):
                    logging.error("UnitTest Execution Error: " + os.path.basename(test))
                    rc = ret
                else:
                    logging.info("UnitTest Completed: " + os.path.basename(test))
                    file_match_pattern = test + ".*." + arch + ".result.xml"
                    xml_results_list = glob.glob(file_match_pattern)
                    for xml_result_file in xml_results_list:
                        root = xml.etree.ElementTree.parse(xml_result_file).getroot()
                        for suite in root:
                            for case in suite:
                                for result in case:
                                    if result.tag == 'failure':
                                        logging.warning("%s Test Failed" % os.path.basename(test))
                                        logging.warning("  %s - %s" % (case.attrib['name'], result.text))

        return rc


    #------------------------------------------------------------------
    #
    # Method to do stuff pre build.
    # This is part of the build flow.
    # Currently do nothing.
    #
    #------------------------------------------------------------------
    def PlatformPreBuild(self):
        rc = 0
        return rc

    #------------------------------------------------------------------
    #
    # Method for the platform to check if a gated build is needed
    # This is part of the build flow.
    # return:
    #  True -  Gated build is needed (default)
    #  False - Gated build is not needed for this platform
    #------------------------------------------------------------------
    def PlatformGatedBuildShouldHappen(self):
        return False

    # Run visual studio batch file and collect the 
    # interesting environment values
    #
    #  Inspiration taken from cpython for this method of env collection
    #
    # vs_path: Path to visual studio install
    # keys: enumerable list with names of env variables to collect after bat run
    # arch: arch to run.  amd64, x86, ??
    #
    # returns a dictionary of the interesting environment variables
    #
    def __Query_Vcvarsall(self, vs_path, keys, arch):
        """Launch vcvarsall.bat and read the settings from its environment"""
        interesting = set(keys)
        result = {}
   
        vcvarsall_path = os.path.join(vs_path, "VC", "Auxiliary", "Build", "vcvarsall.bat")
        logging.debug("Calling '%s %s'", vcvarsall_path, arch)
        popen = subprocess.Popen('"%s" %s & set' % (vcvarsall_path, arch), stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            stdout, stderr = popen.communicate()
            if popen.wait() != 0:
                raise Exception(stderr.decode("mbcs"))
            stdout = stdout.decode("mbcs")
            for line in stdout.split("\n"):
                if '=' not in line:
                    continue
                line = line.strip()
                key, value = line.split('=', 1)
                if key in interesting:
                    if value.endswith(os.pathsep):
                        value = value[:-1]
                    result[key] = value
        finally:
            popen.stdout.close()
            popen.stderr.close()

        if len(result) != len(interesting):
            logging.debug("Input: " + str(sorted(interesting)))
            logging.debug("Result: " + str(sorted(list(result.keys()))))
            raise ValueError(str(list(result.keys())))
        return result

# Smallest 'main' possible. Please don't add unnecessary code.
if __name__ == '__main__':
    # If CommonBuildEntry is not found, the mu_environment pip module has not been installed correctly
    try:
        from MuEnvironment import CommonBuildEntry
    except ImportError:
        raise RuntimeError("Please run \"python -m pip install --upgrade mu_build\".\nContact MS Core UEFI team if you run into any problems.")

    CommonBuildEntry.build_entry(SCRIPT_PATH, WORKSPACE_PATH, REQUIRED_REPOS,
                                 PROJECT_SCOPE, MODULE_PKGS, MODULE_PKG_PATHS,
                                 worker_module='UnitTestBuild')
