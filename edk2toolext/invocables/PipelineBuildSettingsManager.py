from typing import Iterable, Tuple


class PipelineBuildSettingsManager():
    ''' Settings APIs to support an PipelineInvocable

        This is an interface definition only
        to show which functions are required to be implemented
        and can be implemented in a settings manager.
    '''
    pass

    def GetSteps(self) -> Iterable[object]:
        ''' Get the build steps in the build pipeline '''
        return []

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
