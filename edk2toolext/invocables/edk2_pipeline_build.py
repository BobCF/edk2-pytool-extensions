
# @file edk2_pipeline_invocable
# An intermediate class that supports build a pipeline
# invocable process.
#
# Add cmdline parameter handling, a base settings manager class,
# and a Callback.
#
##
# Copyright (c) Microsoft Corporation
#
# SPDX-License-Identifier: BSD-2-Clause-Patent
##
import os
import sys
import logging
import inspect
import pkg_resources
import argparse
from typing import Iterable, Tuple
from edk2toolext import edk2_logging
from edk2toolext.environment import shell_environment
from edk2toollib.utility_functions import GetHostInfo
from edk2toolext.environment import version_aggregator
from edk2toollib.utility_functions import locate_class_in_module
from edk2toollib.utility_functions import import_module_by_file_name
from edk2toolext.edk2_invocable import Edk2InvocableSettingsInterface, Edk2Invocable


class PipelineBuildSettingsManager(Edk2InvocableSettingsInterface):
    ''' Platform settings will be accessed through this implementation. '''

    def GetName(self):
        ''' Get the name of the repo, platform, or product being build '''
        return None

    def GetSteps(self):
        ''' Get the build steps in the build pipeline '''
        return []


class Edk2PipelineInvocable(Edk2Invocable):
    ''' Base class for Multi-Pkg aware invocable '''

    def __init__(self):
        self.requested_architecture_list = []
        self.requested_target_list = []
        super().__init__()

    def AddCommandLineOptions(self, parserObj):
        ''' adds command line options to the argparser '''
        parserObj.add_argument('-a', '--arch', dest="requested_arch", type=str, default=None,
                               help="Optional - CSV of architecutres requested to update. Example: -a X64,AARCH64")
        parserObj.add_argument('-t', '--target', dest='requested_target', type=str, default=None,
                               help="Optional - CSV of targets requested to update.  Example: -t DEBUG,NOOPT")

    def RetrieveCommandLineOptions(self, args):
        '''  Retrieve command line options from the argparser '''

        if args.requested_arch is not None:
            self.requested_architecture_list = args.requested_arch.upper().split(",")
        else:
            self.requested_architecture_list = []

        if args.requested_target is not None:
            self.requested_target_list = args.requested_target.upper().split(",")
        else:
            self.requested_target_list = []

    def InputParametersConfiguredCallback(self):
        ''' This function is called once all the input parameters are collected
            and can be used to initialize environment
        '''
        if(len(self.requested_architecture_list) == 0):
            self.requested_architecture_list = list(self.PlatformSettings.GetArchitecturesSupported())
        self.PlatformSettings.SetArchitectures(self.requested_architecture_list)

        if(len(self.requested_target_list) == 0):
            self.requested_target_list = list(self.PlatformSettings.GetTargetsSupported())
        self.PlatformSettings.SetTargets(self.requested_target_list)

    def Invoke(self):
        ''' Main process function.  Overwrite this function because the pipeline build
            don't need scan the environment and load plugin by itself.
            That part work will be done in build step invocable.
        '''

        self.ParseCommandLineOptions()
        self.ConfigureLogging()
        self.InputParametersConfiguredCallback()

        logging.log(edk2_logging.SECTION, "Start Invocable Tool")
        retcode = self.Go()
        logging.log(edk2_logging.SECTION, "Summary")
        if(retcode != 0):
            logging.error("Error")
        else:
            edk2_logging.log_progress("Success")

        logging.shutdown()
        sys.exit(retcode)

    def Go(self):
        pass
