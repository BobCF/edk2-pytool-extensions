from edk2toolext.invocables.PipelineBuildSettingsManager import PipelineBuildSettingsManager


class PipelineSettingsManager(PipelineBuildSettingsManager):
    def __init__(self):
        super(PipelineSettingsManager, self).__init__()

    def AddPlatformCommandLineOptions(self, parserObj):
        pass


class PipelineBuilder(object):
    def __init__(self):
        pass

    def AddPlatformCommandLineOptions(self, parserObj):
        pass

    def Actions(self):
        pass

    def Go(self):
        print("hello world")
        return 0
