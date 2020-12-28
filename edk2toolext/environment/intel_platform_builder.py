# @file intel_build.py
# This module contains code that supports the Intel Platform prebuild
# and postbuild steps
# This class is designed to be subclassed by a buildstep to allow
# more extensive and custom behavior.
##
# Copyright (c) Microsoft Corporation
#
# SPDX-License-Identifier: BSD-2-Clause-Patent
##


import os
import logging
from edk2toolext.environment.multiple_workspace import MultipleWorkspace
from edk2toolext.environment import conf_mgmt
import traceback
import shutil
import time
from edk2toolext.environment import shell_environment
from edk2toollib.utility_functions import RunCmd
from edk2toolext import edk2_logging
from edk2toolext.environment.plugintypes.uefi_build_plugin import IUefiBuildPlugin
import datetime
from edk2toolext.environment.pipeline_builder import PipelineSettingsManager
from edk2toolext.environment.pipeline_builder import PipelineBuilder


class IntelBuilder(PipelineBuilder):

    def __init__(self):
        self.SkipBuild = False
        self.SkipPreBuild = False
        self.SkipPostBuild = False
        self.ShowHelpOnly = False
        self.OutputBuildEnvBeforeBuildToFile = None
        self.Clean = False
        self.UpdateConf = False
        self.OutputConfig = None

    def AddPlatformCommandLineOptions(self, parserObj):
        ''' adds command line options to the argparser '''
        parserObj.add_argument("--SKIPBUILD", "--skipbuild", "--SkipBuild", dest="SKIPBUILD",
                               action='store_true', default=False, help="Skip the build process")
        parserObj.add_argument("--SKIPPREBUILD", "--skipprebuild", "--SkipPrebuild", dest="SKIPPREBUILD",
                               action='store_true', default=False, help="Skip prebuild process")
        parserObj.add_argument("--SKIPPOSTBUILD", "--skippostbuild", "--SkipPostBuild", dest="SKIPPOSTBUILD",
                               action='store_true', default=False, help="Skip postbuild process")
        parserObj.add_argument("--UPDATECONF", "--updateconf", "--UpdateConf",
                               dest="UPDATECONF", action='store_true', default=False,
                               help="Update Conf. Builders Conf files will be replaced with latest template files")
        parserObj.add_argument("--CLEAN", "--clean", "--CLEAN", dest="CLEAN",
                               action='store_true', default=False,
                               help="Clean. Remove all old build artifacts and intermediate files")
        parserObj.add_argument("--CLEANONLY", "--cleanonly", "--CleanOnly", dest="CLEANONLY",
                               action='store_true', default=False,
                               help="Clean Only. Do clean operation and don't build just exit.")
        parserObj.add_argument("--OUTPUTCONFIG", "--outputconfig", "--OutputConfig",
                               dest='OutputConfig', required=False, type=str,
                               help='Provide shell variables in a file')

    def RetrievePlatformCommandLineOptions(self, args):
        '''  Retrieve command line options from the argparser'''
        self.OutputConfig = os.path.abspath(args.OutputConfig) if args.OutputConfig else None

        if(args.SKIPBUILD):
            self.SkipBuild = True
        elif(args.SKIPPREBUILD):
            self.SkipPreBuild = True
        elif(args.SKIPPOSTBUILD):
            self.SkipPostBuild = True
        elif(args.UPDATECONF):
            self.UpdateConf = True
        elif(args.CLEAN):
            self.Clean = True
        elif(args.CLEANONLY):
            self.Clean = True
            self.SkipBuild = True
            self.SkipPreBuild = True
            self.SkipPostBuild = True

    def Go(self, WorkSpace, PackagesPath, PInHelper, PInManager):
        self.env = shell_environment.GetBuildVars()
        self.mws = MultipleWorkspace()
        self.mws.setWs(WorkSpace, PackagesPath)
        self.ws = WorkSpace
        self.pp = PackagesPath  # string using os.pathsep
        self.Helper = PInHelper
        self.pm = PInManager

        try:
            edk2_logging.log_progress("Start time: {0}".format(datetime.datetime.now()))
            start_time = time.perf_counter()

            self.Helper.DebugLogRegisteredFunctions()

            ret = self.SetEnv()
            if(ret != 0):
                logging.critical("SetEnv failed")
                return ret

            # clean
            if(self.Clean):
                edk2_logging.log_progress("Cleaning")
                ret = self.CleanTree()
                if(ret != 0):
                    logging.critical("Clean failed")
                    return ret

            # prebuild
            if(self.SkipPreBuild):
                edk2_logging.log_progress("Skipping Pre Build")
            else:
                ret = self.PreBuild()
                if(ret != 0):
                    logging.critical("Pre Build failed")
                    return ret

            # Output Build Environment to File - this is mostly for debug of build
            # issues or adding other build features using existing variables
            if(self.OutputConfig is not None):
                edk2_logging.log_progress("Writing Build Env Info out to File")
                logging.debug("Found an Output Build Env File: " + self.OutputConfig)
                self.env.PrintAll(self.OutputConfig)

            # build
            if(self.SkipBuild):
                edk2_logging.log_progress("Skipping Build")
            else:
                ret = self.Build()
                if(ret != 0):
                    logging.critical("Build failed")
                    return ret

            # postbuild
            if(self.SkipPostBuild):
                edk2_logging.log_progress("Skipping Post Build")
            else:
                ret = self.PostBuild()
                if(ret != 0):
                    logging.critical("Post Build failed")
                    return ret

        except:
            logging.critical("Build Process Exception")
            logging.error(traceback.format_exc())
            return -1
        finally:
            end_time = time.perf_counter()
            elapsed_time_s = int((end_time - start_time))
            edk2_logging.log_progress("End time: {0}\t Total time Elapsed: {1}".format(
                datetime.datetime.now(), datetime.timedelta(seconds=elapsed_time_s)))

        return 0

    def CleanTree(self, RemoveConfTemplateFilesToo=False):
        ret = 0
        # loop thru each build target set.
        edk2_logging.log_progress("Cleaning All Output for Build")

        d = self.env.GetValue("BUILD_OUTPUT_BASE")
        if(os.path.isdir(d)):
            logging.debug("Removing [%s]", d)
            # if the folder is opened in Explorer do not fail the entire Rebuild
            try:
                shutil.rmtree(d)
            except WindowsError as wex:
                logging.debug(wex)

        else:
            logging.debug("Directory [%s] already clean" % d)

        return ret

    #
    # Build step
    #

    def Build(self):
        return 0

    def PreBuild(self):
        edk2_logging.log_progress("Running Pre Build")
        #
        # Run the platform pre-build steps.
        #
        ret = self.PlatformPreBuild()

        if(ret != 0):
            logging.critical("PlatformPreBuild failed %d" % ret)
            return ret
        #
        # run all loaded UefiBuild Plugins
        #
        for Descriptor in self.pm.GetPluginsOfClass(IUefiBuildPlugin):
            rc = Descriptor.Obj.do_pre_build(self)
            if(rc != 0):
                if(rc is None):
                    logging.error(
                        "Plugin Failed: %s returned NoneType" % Descriptor.Name)
                    ret = -1
                else:
                    logging.error("Plugin Failed: %s returned %d" %
                                  (Descriptor.Name, rc))
                    ret = rc
                break  # fail on plugin error
            else:
                logging.debug("Plugin Success: %s" % Descriptor.Name)
        return ret

    def PostBuild(self):
        edk2_logging.log_progress("Running Post Build")
        #
        # Run the platform post-build steps.
        #
        ret = self.PlatformPostBuild()

        if(ret != 0):
            logging.critical("PlatformPostBuild failed %d" % ret)
            return ret

        #
        # run all loaded UefiBuild Plugins
        #
        for Descriptor in self.pm.GetPluginsOfClass(IUefiBuildPlugin):
            rc = Descriptor.Obj.do_post_build(self)
            if(rc != 0):
                if(rc is None):
                    logging.error(
                        "Plugin Failed: %s returned NoneType" % Descriptor.Name)
                    ret = -1
                else:
                    logging.error("Plugin Failed: %s returned %d" %
                                  (Descriptor.Name, rc))
                    ret = rc
                break  # fail on plugin error
            else:
                logging.debug("Plugin Success: %s" % Descriptor.Name)

        return ret

    def SetEnv(self):
        edk2_logging.log_progress("Setting up the Environment")
        shell_environment.GetEnvironment().set_shell_var("WORKSPACE", self.ws)
        shell_environment.GetBuildVars().SetValue("WORKSPACE", self.ws, "Set in SetEnv")

        if(self.pp is not None):
            shell_environment.GetEnvironment().set_shell_var("PACKAGES_PATH", self.pp)
            shell_environment.GetBuildVars().SetValue(
                "PACKAGES_PATH", self.pp, "Set in SetEnv")

        # process platform parameters defined in platform build file
        ret = self.SetPlatformEnv()
        if(ret != 0):
            logging.critical("Set Platform Env failed")
            return ret

        # set build output base envs for all builds
        if self.env.GetValue("OUTPUT_DIRECTORY") is None:
            logging.warn("OUTPUT_DIRECTORY was not found, defaulting to Build")
            self.env.SetValue("OUTPUT_DIRECTORY", "Build", "default from uefi_build", True)

        # BUILD_OUT_TEMP is a path so the value should use native directory separators
        self.env.SetValue("BUILD_OUT_TEMP",
                          os.path.normpath(os.path.join(self.ws, self.env.GetValue("OUTPUT_DIRECTORY"))),
                          "Computed in SetEnv")

        target = self.env.GetValue("TARGET")
        self.env.SetValue("BUILD_OUTPUT_BASE", os.path.join(self.env.GetValue(
            "BUILD_OUT_TEMP"), target + "_" + self.env.GetValue("TOOL_CHAIN_TAG")), "Computed in SetEnv")

        # We have our build target now.  Give platform build one more chance for target specific settings.
        ret = self.SetPlatformEnvAfterTarget()
        if(ret != 0):
            logging.critical("SetPlatformEnvAfterTarget failed")
            return ret

        # set the build report file
        self.env.SetValue("BUILDREPORT_FILE", os.path.join(
            self.env.GetValue("BUILD_OUTPUT_BASE"), "BUILD_REPORT.TXT"), True)

        return 0

    # -----------------------------------------------------------------------
    # Methods that will be overridden by child class
    # -----------------------------------------------------------------------

    @classmethod
    def PlatformPreBuild(self):
        return 0

    @classmethod
    def PlatformPostBuild(self):
        return 0

    @classmethod
    def SetPlatformEnv(self):
        return 0

    @classmethod
    def SetPlatformEnvAfterTarget(self):
        return 0

    @classmethod
    def PlatformBuildRom(self):
        return 0

    @classmethod
    def PlatformFlashImage(self):
        return 0

    @classmethod
    def PlatformGatedBuildShouldHappen(self):
        return True

    # ------------------------------------------------------------------------
    #  HELPER FUNCTIONS
    # ------------------------------------------------------------------------
    #
