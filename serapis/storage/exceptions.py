'''
Created on Oct 27, 2014

@author: ic4
'''
from serapis.controller import exceptions

class BackendException(exceptions.SerapisException):
    ''' Exception raised when the backend operations failed.
        Attributes:
            values : the values that caused the exception to be thrown
            message : the error message
     '''
    pass

class NoAccessException(BackendException):
    ''' Exception raised when the user doesn't have access to the wanted file/coll in iRODS.'''
    def __init__(self, values=[], message='No access'):
        super(NoAccessException, self).__init__(values, message)


class OverwriteWithoutForceFlagException(BackendException):
    ''' 
        Exception thrown when a file is uploaded, but there is already one in the destination collection with the same name.
        It corresponds to OVERWRITE_WITHOUT_FORCE_FLAG irods error output. 
    '''
    def __init__(self, values=[], message='Overwrite without force flag is not allowed'):
        super(OverwriteWithoutForceFlagException, self).__init__(values, message)


class FileReplicaNotPairedException(BackendException):
    ''' Exception thrown when a file has one or more replicas not paired.'''
    def __init__(self, values=[], message='This file has one or more replicas not paired'):
        super(FileReplicaNotPairedException, self).__init__(values, message)


class FileMissingReplicaException(BackendException):
    ''' Exception thrown when a file has not been replicated.'''
    def __init__(self, values=[], message='This file should have been replicated'):
        super(FileMissingReplicaException, self).__init__(values, message)


class FileHasTooManyReplicasException(BackendException):
    ''' Exception thrown when a file has too many replicas.'''
    def __init__(self, values=[], message='This file has more replicas than permitted'):
        super(FileHasTooManyReplicasException, self).__init__(values, message)


class FileStoredOnResourceUnknownException(BackendException):
    ''' Exception thrown when a file is stored on 
        an unknown resource - probably other than red/green.'''
    def __init__(self, values=[], message='This file appears on an unknown resource '):
        super(FileStoredOnResourceUnknownException, self).__init__(values, message)


class FileNotBackedupOnBothRescGrps(BackendException):
    ''' Exception thrown when a file hasn't got replicas on both red and green resource groups.'''
    def __init__(self, values=[], message='This file is not backed up on both resource groups'):
        super(FileNotBackedupOnBothRescGrps, self).__init__(values, message)
    

class DifferentFileMD5sException(BackendException):
    ''' Exception thrown when a file has a different md5 
        than the calculated md5 by serapis.
    '''
    def __init__(self, values=[], message='This file appears to have a different md5 in iRODS than it had on the client'):
        super(DifferentFileMD5sException, self).__init__(values, message)
    

class FileMetadataNotStardardException(BackendException):
    ''' Exception thrown when a file's metadata is not how it's supposed to be
        e.g. either it is missing fields or it has too many fields of one kind.'''
    def __init__(self, values=[], message='This file has metadata that is not standard'):
        super(FileMetadataNotStardardException, self).__init__(values, message)
    

class FileMetadataMissingException(BackendException):
    ''' 
        Exception thrown when some or all of the file's metadata is missing for some reason.
    '''
    def __init__(self, values=[], message='This file is missing one or more metadata AVUs'):
        super(FileMetadataMissingException, self).__init__(values, message)


class FileMetadataCannotBeAdded(BackendException):
    ''' This exception is thrown when an attempt to add 
        metadata to a file fails for some reason.
    '''
    def __init__(self, values=[], reasons={}, message='File metadata could not be added'):
        self.reasons = reasons
        super(FileMetadataCannotBeAdded, self).__init__(values, message)
        

class FileMetadataCannotBeRemoved(BackendException):
    ''' This exception is thrown when an attempt to remove 
        metadata to a file fails for some reason.
    '''
    def __init__(self, values=[], reasons={}, message='File metadata could not be removed'):
        self.reasons = reasons
        super(FileMetadataCannotBeRemoved, self).__init__(values, message)




class AlreadyExisting(BackendException):
    ''' 
        Exception thrown when the system tries to upload a file or create a directory,
        but there is already a file/dir with the same name in the destination collection.
        It corresponds to OVERWRITE_WITHOUT_FORCE_FLAG irods error output. 
    '''
    def __init__(self, values=[], message='This file already exists at the given path'):
        super(AlreadyExisting, self).__init__(values, message)


class FileAlreadyExisting(BackendException):
    ''' 
        Exception thrown when the system tries to upload a file or create a directory,
        but there is already a file/dir with the same name in the destination collection.
        It corresponds to OVERWRITE_WITHOUT_FORCE_FLAG irods error output. 
    '''
    def __init__(self, values=[], message='This file already exists at the given path'):
        super(FileAlreadyExisting, self).__init__(values, message)


class DirectoryAlreadyExisting(BackendException):
    ''' 
        Exception thrown when a collection is intended to be created, but there is already one 
        in the destination collection with the same name.
        It corresponds to CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME irods error output. 
    '''
    def __init__(self, values=[], message='This directory already exists'):
        super(DirectoryAlreadyExisting, self).__init__(values, message)


class InvalidArgumentException(BackendException):
    ''' 
        This exception is thrown when there was an invalid argument provided to a function 
        that executes commands on the backend.
    '''
    def __init__(self, values=[], message='Invalid argument provided'):
        super(InvalidArgumentException, self).__init__(values, message)
       



#v         CAT_INVALID_ARGUMENT        = "CAT_INVALID_ARGUMENT"
# 
#v CAT_NO_ACCESS_PERMISSION    = "CAT_NO_ACCESS_PERMISSION"
# 
#v CAT_SUCCESS_BUT_WITH_NO_INFO = "CAT_SUCCESS_BUT_WITH_NO_INFO"
# 
#-- CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME = "CATALOG_ALREADY_HAS_ITEM_BY_THAT_NAME"
# 
# ------can go into the InvalidArgException--- USER_INPUT_PATH_ERR = "USER_INPUT_PATH_ERR"
# 
#v OVERWRITE_WITHOUT_FORCE_FLAG = "OVERWRITE_WITHOUT_FORCE_FLAG"
# 
#V CHKSUM_ERROR = "chksum error"
# 
#XXX USER_INPUT_OPTION_ERR = "USER_INPUT_OPTION_ERR"

