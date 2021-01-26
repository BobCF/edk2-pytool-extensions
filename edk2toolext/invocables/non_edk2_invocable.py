
# @file edk2_platform_build
# Invocable class that does a build.
# Needs a child of UefiBuilder for pre/post build steps.
##
# Copyright (c) Microsoft Corporation
#
# SPDX-License-Identifier: BSD-2-Clause-Patent
##
import os
import sys
import logging
import argparse
import inspect
from typing import Iterable, Tuple
from edk2toolext import edk2_logging
from edk2toolext.environment import plugin_manager
from edk2toolext.environment import shell_environment
from edk2toolext.environment.plugintypes.uefi_helper_plugin import HelperFunctions
from edk2toolext.environment import self_describing_environment
from edk2toollib.utility_functions import locate_class_in_module
from edk2toollib.utility_functions import import_module_by_file_name
from edk2toollib.uefi.edk2.path_utilities import Edk2Path
from edk2toolext.base_abstract_invocable import BaseAbstractInvocable
from edk2toolext.environment.non_edk2_builder import NonEdk2Builder


def build_env_changed(build_env, build_env_2):
    ''' return True if build_env has changed '''

    return (build_env.paths != build_env_2.paths) or \
           (build_env.extdeps != build_env_2.extdeps) or \
           (build_env.plugins != build_env_2.plugins)


class NonEdk2BuildSettingsManager():
    ''' Settings APIs to support an Edk2Invocable

        This is an interface definition only
        to show which functions are required to be implemented
        and can be implemented in a settings manager.
    '''

    def GetWorkspaceRoot(self) -> str:
        ''' get absolute path to WorkspaceRoot '''
        raise NotImplementedError()

    def GetActiveScopes(self) -> Tuple[str]:
        ''' Optional API to return Tuple containing scopes that should be active for this process '''
        return ()

    def GetLoggingLevel(self, loggerType: str) -> str:
        ''' Get the logging level for a given type
        base == lowest logging level supported
        con  == Screen logging
        txt  == plain text file logging
        md   == markdown file logging
        '''
        return None

    def AddCommandLineOptions(self, parserObj: object) -> None:
        ''' Implement in subclass to add command line options to the argparser '''
        pass

    def RetrieveCommandLineOptions(self, args: object) -> None:
        '''  Implement in subclass to retrieve command line options from the argparser namespace '''
        pass


class NonEdk2Build(BaseAbstractInvocable):
    ''' Imports UefiBuilder and calls go '''

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
            self.PlatformBuilder = locate_class_in_module(self.PlatformModule, NonEdk2Builder)()
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
                pass
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
        # self.PlatformBuilder.AddCommandLineOptions(parserObj)

        default_build_config_path = os.path.join(self.GetWorkspaceRoot(), "BuildConfig.conf")

        # add the common stuff that everyone will need
        parserObj.add_argument('--build-config', dest='build_config', default=default_build_config_path, type=str,
                               help='Provide shell variables in a file')
        parserObj.add_argument('--verbose', '--VERBOSE', '-v', dest="verbose", action='store_true', default=False,
                               help='verbose')

        # setup sys.argv and argparse round 2
        sys.argv = [sys.argv[0]] + unknown_args
        args, unknown_args = parserObj.parse_known_args()
        self.Verbose = args.verbose

        # give the parsed args to the subclass
        self.RetrieveCommandLineOptions(args)

        # give the parsed args to platform settings manager
        # self.PlatformBuilder.RetrieveCommandLineOptions(args)

        #
        # Look through unknown_args and BuildConfig for strings that are x=y,
        # set env.SetValue(x, y),
        # then remove this item from the list.
        #
        env = shell_environment.GetBuildVars()
        BuildConfig = os.path.abspath(args.build_config)

        for argument in unknown_args:
            if argument.count("=") != 1:
                raise RuntimeError(f"Unknown variable passed in via CLI: {argument}")
            tokens = argument.strip().split("=")
            env.SetValue(tokens[0].strip().upper(), tokens[1].strip(), "From CmdLine")

        unknown_args.clear()  # remove the arguments we've already consumed

        if os.path.isfile(BuildConfig):
            with open(BuildConfig) as file:
                for line in file:
                    stripped_line = line.strip().partition("#")[0]
                    if len(stripped_line) == 0:
                        continue
                    unknown_args.append(stripped_line)

        for argument in unknown_args:
            if argument.count("=") != 1:
                raise RuntimeError(f"Unknown variable passed in via BuildConfig: {argument}")
            tokens = argument.strip().split("=")
            env.SetValue(tokens[0].strip().upper(), tokens[1].strip(), "From BuildConf")

    def AddCommandLineOptions(self, parserObj):
        ''' adds command line options to the argparser '''

        self.PlatformBuilder.AddPlatformCommandLineOptions(parserObj)

    def RetrieveCommandLineOptions(self, args):
        '''  Retrieve command line options from the argparser '''
        self.PlatformBuilder.RetrievePlatformCommandLineOptions(args)

    def GetSettingsClass(self):
        '''  Providing BuildSettingsManager  '''
        return NonEdk2BuildSettingsManager

    def GetLoggingFileName(self, loggerType):
        name = self.PlatformBuilder.GetName()
        if name is not None:
            return f"BUILDLOG_{name}"
        return "BUILDLOG"

    def GetWorkspaceRoot(self) -> os.PathLike:
        try:
            wp = self.PlatformBuilder.GetWorkspaceRoot()
        except AttributeError:
            raise RuntimeError("Can't call this before PlatformBuilder has been set up!")

        if not wp:
            raise RuntimeError("Not set Workspace Root")

        return wp

    def GetActiveScopes(self) -> Tuple[str]:
        ''' Optional API to return Tuple containing scopes that should be active for this process '''
        return ()

    def GetLoggingLevel(self, loggerType):
        ''' Get the logging level for a given type
        base == lowest logging level supported
        con  == Screen logging
        txt  == plain text file logging
        md   == markdown file logging
        '''
        try:
            level = self.PlatformBuilder.GetLoggingLevel(loggerType)
            if level is not None:
                return level
        except:
            pass

        if(loggerType == "con") and not self.Verbose:
            return logging.WARNING
        return logging.DEBUG

    def GetLoggingFolderRelativeToRoot(self):
        return "Build"

    def PerformUpdate(self):
        ws_root = self.GetWorkspaceRoot()
        scopes = self.GetActiveScopes()
        (build_env, shell_env) = self_describing_environment.BootstrapEnvironment(ws_root, scopes)
        (success, failure) = self_describing_environment.UpdateDependencies(ws_root, scopes)
        if success != 0:
            logging.log(edk2_logging.SECTION, f"\tUpdated/Verified {success} dependencies")
        return (build_env, shell_env, failure)

    def update_ext_deps(self):
        MAX_RETRY_COUNT = 10
        # Get the environment set up.
        RetryCount = 0
        failure_count = 0
        logging.log(edk2_logging.SECTION, "Initial update of environment")

        (build_env_old, shell_env_old, _) = self.PerformUpdate()
        self_describing_environment.DestroyEnvironment()

        # Loop updating dependencies until there are 0 new dependencies or
        # we have exceeded retry count.  This allows dependencies to carry
        # files that influence the SDE.
        logging.log(edk2_logging.SECTION, "Second pass update of environment")
        while RetryCount < MAX_RETRY_COUNT:
            (build_env, shell_env, failure_count) = self.PerformUpdate()

            if not build_env_changed(build_env, build_env_old):  # check if the environment changed on our last update
                break
            # if the environment has changed, increment the retry count and notify user
            RetryCount += 1
            logging.log(edk2_logging.SECTION,
                        f"Something in the environment changed. Updating environment again. Pass {RetryCount}")

            build_env_old = build_env
            self_describing_environment.DestroyEnvironment()

        if failure_count != 0:
            logging.error(f"We were unable to successfully update {failure_count} dependencies in environment")
        if RetryCount >= MAX_RETRY_COUNT:
            logging.error(f"We did an update more than {MAX_RETRY_COUNT} times.")
            logging.error("Please check your dependencies and make sure you don't have any circular ones.")
            return 1

        return failure_count

    def Go(self):
        logging.info("Running Python version: " + str(sys.version_info))

        (build_env, shell_env) = self_describing_environment.BootstrapEnvironment(
            self.GetWorkspaceRoot(), self.GetActiveScopes())

        # PYTHON_COMMAND is required to be set for using edk2 python builds.
        # todo: work with edk2 to remove the bat file and move to native python calls
        pc = sys.executable
        if " " in pc:
            pc = '"' + pc + '"'
        shell_env.set_shell_var("PYTHON_COMMAND", pc)

        # Load plugins
        logging.log(edk2_logging.SECTION, "Loading Plugins")
        pm = plugin_manager.PluginManager()
        failedPlugins = pm.SetListOfEnvironmentDescriptors(
            build_env.plugins)
        if failedPlugins:
            logging.critical("One or more plugins failed to load. Halting build.")
            for a in failedPlugins:
                logging.error("Failed Plugin: {0}".format(a["name"]))
            raise Exception("One or more plugins failed to load.")

        helper = HelperFunctions()
        if(helper.LoadFromPluginManager(pm) > 0):
            raise Exception("One or more helper plugins failed to load.")

        #
        # Now we can actually kick off a build.
        #
        logging.log(edk2_logging.SECTION, "Kicking off build")
        self.update_ext_deps()
        ret = self.PlatformBuilder.Go()
        logging.log(edk2_logging.SECTION, f"Log file is located at: {self.log_filename}")
        return ret


def main():
    NonEdk2Build().Invoke()


if __name__ == "__main__":
    main()
