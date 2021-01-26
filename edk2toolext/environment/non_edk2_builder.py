from edk2toolext.invocables.edk2_update import Edk2Update, build_env_changed
import logging
from edk2toolext import edk2_logging
from edk2toolext.environment import self_describing_environment


class NonEdk2Builder(Edk2Update):

    # TODO: this initiablize block should go to pipeline builder
    def initialize(self, ActionConfig):
        self.type = ActionConfig.type
        self.module = ActionConfig.module
        self.builder_class = ActionConfig.builder_class
        self.ext_deps = ActionConfig.ext_deps
        self.plugins = ActionConfig.plugins
        self.dependnecies = ActionConfig.dependnecies
        self.output = ActionConfig.output
        self.workspace = ActionConfig.workspace

    def AddPlatformCommandLineOptions(self, parserObj):
        pass

    def RetrievePlatformCommandLineOptions(self, args):
        pass

    def execute(self):
        raise NotImplementedError

    def Go(self):
        self.execute()
        return 0

    def GetWorkspaceRoot(self):
        pass
        # TODO: output folder design
