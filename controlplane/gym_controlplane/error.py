class Error(Exception):
    pass

class UserError(Error):
    def __init__(self, message):
        super(UserError, self).__init__(message)
        self.user_message = message

class UnregisteredCollection(UserError):
    pass

class UnregisteredEnv(UserError):
    """Raised when the user requests an env from the registry that does
    not actually exist.
    """
    def __init__(self, message, path):
        super(UnregisteredEnv, self).__init__(message)
        self.path = path

        self.user_message = 'No server-side registration for env (missing path {})'.format(path)

class VExpectTimeout(Error):
    pass
