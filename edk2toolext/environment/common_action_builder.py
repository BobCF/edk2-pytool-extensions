from edk2toolext.invocables.edk2_update import Edk2Update


class ActionBuilder(Edk2Update):

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

    def Go(self):
        self.update_ext_deps()

    def GetWorkspaceRoot(self):
        pass
        # TODO: output folder design

    def update_ext_deps(self):
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
        while RetryCount < Edk2Update.MAX_RETRY_COUNT:
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
        if RetryCount >= Edk2Update.MAX_RETRY_COUNT:
            logging.error(f"We did an update more than {Edk2Update.MAX_RETRY_COUNT} times.")
            logging.error("Please check your dependencies and make sure you don't have any circular ones.")
            return 1

        return failure_count
