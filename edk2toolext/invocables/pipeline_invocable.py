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
from edk2toolext.base_abstract_invocable import BaseAbstractInvocable
from edk2toolext.invocables.PipelineBuildSettingsManager import PipelineBuildSettingsManager
from edk2toolext.environment.pipeline_builder import PipelineBuilder


class Edk2PipelineInvocable(BaseAbstractInvocable):

    def __init__(self):
        self.requested_architecture_list = []
        self.requested_target_list = []
        super().__init__()

    def GetSettingsClass(self):
        '''  Providing BuildSettingsManager  '''
        return PipelineBuildSettingsManager

    def ParseCommandLineOptions(self):
        '''
        Parses command line options.
        Sets up argparser specifically to get PlatformSettingsManager instance.
        Then sets up second argparser and passes it to child class and to PlatformSettingsManager.
        Finally, parses all known args and then reads the unknown args in to build vars.
        '''
        # first argparser will only get settings manager and help will be disabled
        settingsParserObj = argparse.ArgumentParser(add_help=False)
        # instantiate the second argparser that will get passed around

        epilog = '''
<key>=<value>               - Set an env variable for the pre/post build process
BLD_*_<key>=<value>         - Set a build flag for all build types.
Key=value will get passed to build process
BLD_<TARGET>_<key>=<value>  - Set a build flag for build type of <target>
Key=value will get passed to build process for given build type)'''

        parserObj = argparse.ArgumentParser(epilog=epilog)

        settingsParserObj.add_argument('-c', '--platform_module', dest='platform_module',
                                       default="PlatformBuild.py", type=str,
                                       help='Provide the Platform Module relative to the current working directory.'
                                            f'This should contain a {self.GetSettingsClass().__name__} instance.')

        # get the settings manager from the provided file and load an instance
        settingsArg, unknown_args = settingsParserObj.parse_known_args()
        try:
            self.PlatformModule = import_module_by_file_name(os.path.abspath(settingsArg.platform_module))
            self.PlatformSettings = locate_class_in_module(
                self.PlatformModule, self.GetSettingsClass())()
        except (TypeError):
            # Gracefully exit if the file we loaded isn't the right type
            class_name = self.GetSettingsClass().__name__
            print(f"Unable to use {settingsArg.platform_module} as a {class_name}")
            print("Did you mean to use a different kind of invocable?")
            try:
                # If this works, we can provide help for whatever special functions
                # the subclass is offering.
                self.AddCommandLineOptions(settingsParserObj)
                Module = self.PlatformModule
                module_contents = dir(Module)
                # Filter through the Module, we're only looking for classes.
                classList = [getattr(Module, obj) for obj in module_contents if inspect.isclass(getattr(Module, obj))]
                # Get the name of all the classes
                classNameList = [obj.__name__ for obj in classList]
                # TODO improve filter to no longer catch imports as well as declared classes
                imported_classes = ", ".join(classNameList)  # Join the classes together
                print(f"The module you imported contains {imported_classes}")
            except Exception:
                # Otherwise, oh well we'll just ignore this.
                raise
            settingsParserObj.print_help()
            sys.exit(1)

        except (FileNotFoundError):
            # Gracefully exit if we can't find the file
            print(f"We weren't able to find {settingsArg.platform_module}")
            settingsParserObj.print_help()
            sys.exit(2)

        except Exception as e:
            print(f"Error: We had trouble loading {settingsArg.platform_module}. Is the path correct?")
            # Gracefully exit if setup doesn't go well.
            settingsParserObj.print_help()
            print(e)
            sys.exit(2)

        # now to get the big arg parser going...
        # first pass it to the subclass
        self.AddCommandLineOptions(parserObj)

        # next pass it to the settings manager
        self.PlatformSettings.AddCommandLineOptions(parserObj)

        # add the common stuff that everyone will need
        parserObj.add_argument('--verbose', '--VERBOSE', '-v', dest="verbose", action='store_true', default=False,
                               help='verbose')

        # setup sys.argv and argparse round 2
        sys.argv = [sys.argv[0]] + unknown_args
        args, unknown_args = parserObj.parse_known_args()
        self.Verbose = args.verbose

        # give the parsed args to the subclass
        self.RetrieveCommandLineOptions(args)

        # give the parsed args to platform settings manager
        self.PlatformSettings.RetrieveCommandLineOptions(args)

        #
        # Look through unknown_args and BuildConfig for strings that are x=y,
        # set env.SetValue(x, y),
        # then remove this item from the list.
        #
        env = shell_environment.GetBuildVars()

        for argument in unknown_args:
            if argument.count("=") != 1:
                raise RuntimeError(f"Unknown variable passed in via CLI: {argument}")
            tokens = argument.strip().split("=")
            env.SetValue(tokens[0].strip().upper(), tokens[1].strip(), "From CmdLine")

        unknown_args.clear()  # remove the arguments we've already consumed

        for argument in unknown_args:
            if argument.count("=") != 1:
                raise RuntimeError(f"Unknown variable passed in via BuildConfig: {argument}")
            tokens = argument.strip().split("=")
            env.SetValue(tokens[0].strip().upper(), tokens[1].strip(), "From BuildConf")

    def GetWorkspaceRoot(self):
        # TODO: implement it
        return self.PlatformSettings.GetWorkspaceRoot()

    def GetActiveScopes(self) -> Tuple[str]:
        ''' Use the SettingsManager to return tuple containing scopes that should be active for this process.'''
        try:
            scopes = self.PlatformSettings.GetActiveScopes()
        except AttributeError:
            raise RuntimeError("Can't call this before PlatformSettings has been set up!")

        # Add any OS-specific scope.
        if GetHostInfo().os == "Windows":
            scopes += ('global-win',)
        elif GetHostInfo().os == "Linux":
            scopes += ('global-nix',)
        # Add the global scope. To be deprecated.
        scopes += ('global',)
        return scopes

    def GetLoggingLevel(self, loggerType):
        ''' Get the logging level for a given type
        base == lowest logging level supported
        con  == Screen logging
        txt  == plain text file logging
        md   == markdown file logging
        '''
        try:
            level = self.PlatformSettings.GetLoggingLevel(loggerType)
            if level is not None:
                return level
        except Exception as e:
            print(e)

        if(loggerType == "con") and not self.Verbose:
            return logging.WARNING

    def GetLoggingFolderRelativeToRoot(self):
        return "Build"

        # TODO:
        # init the pipeline settingsmanager

    def GetLoggingFileName(self, file_type):
        return "build_log." + file_type

    def AddCommandLineOptions(self, parserObj):
        ''' adds command line options to the argparser '''
        # PlatformSettings could also be a subclass of UefiBuilder, who knows!
        if isinstance(self.PlatformSettings, PipelineBuilder):
            self.PlatformBuilder = self.PlatformSettings
        else:
            try:
                # if it's not, we will try to find it in the module that was originally provided.
                self.PlatformBuilder = locate_class_in_module(self.PlatformModule, UefiBuilder)()
            except (TypeError):
                raise RuntimeError(f"UefiBuild not found in module:\n{dir(self.PlatformModule)}")

        self.PlatformBuilder.AddPlatformCommandLineOptions(parserObj)

    def RetrieveCommandLineOptions(self, args):
        '''  Retrieve command line options from the argparser '''
        pass

    def InputParametersConfiguredCallback(self):
        ''' This function is called once all the input parameters are collected
            and can be used to initialize environment
        '''
        pass

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
        # TODO: instanaces the pipeline builder and launch steps
        #
        return self.PlatformBuilder.Go()


def main():
    Edk2PipelineInvocable().Invoke()


if __name__ == "__main__":
    main()
