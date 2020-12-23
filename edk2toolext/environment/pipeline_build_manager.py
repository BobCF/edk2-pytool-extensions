class BuildManager():
    ''' This class define the interface for build management. The build step settings manager 
    need to implement those interfaces. '''

    def InputList(self):
        pass

    def OutputList(self):
        pass

    def EnableCache(self):
        pass
