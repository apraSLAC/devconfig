
class Error(Exception):
    """Base class for exceptions in this module."""
    pass

# General Errors

class NotImplementedError(Error)
	"""
	Exception raised if there is an attempt to use a feature that hasn't been
	implemented yet.
	"""
	def __str__(self):
		return repr("This feature has not been implemented yet.")

class typeError(Error):
	"""Exception raised if an improper type was inputted."""
	def __init__(self, correctType):
		self.correctType = correctType
	def __str__(self):
		return repr("Type {1} needed.".format(self.correctType))

class InvalidPathError(Error):
	"""Exception raised if the path to a file does not exist."""
	def __init__(self, path):
		self.path = path
	def __str__(self):
		return repr("Invalid path used: {0}.".format(self.path))	

# devconfig Errors
class LocalModeEnabled(Error):
	"""
	Exception raised if an attempted action requires LocalMode to be False but is
	set to True.
	"""
	def __str__(self):
		return repr("This operation requires devconfig to not be in local mode.")

class LocalModeDisabled(Error):
	"""
	Exception raised if an attempted action requires LocalMode to be True but is
	set to False.
	"""
	def __str__(self):
		return repr("This operation requires devconfig to be in local mode.")

# Hutch Errors
class InvalidHutchError(Error):
	"""Exception raised if an inputted hutch is not part of _allHutches."""
	def __init__(self, hutchEntry):
		self.hutchEntry = hutchEntry
	def __str__(self):
		return repr("Invalid Hutch(es) Inputted: {0}".format(self.hutchEntry))

# class NoValidHutchError(Error):
# 	"""Exception raised if none of the hutch inputs are valid."""
# 	def __init__(self, hutchEntries):
# 		self.hutchEntries = hutchEntries
# 	def __str__(self):
# 		return repr(

# objType Errors
class InvalidObjTypeError(Error):
	"""Exception raised if an inputted objType is not part of _allObjTypes."""
	def __init__(self, objTypeEntry):
		self.objTypeEntry = objTypeEntry
	def __str__(self):
		return repr("Invalid ObjType(s) Inputted: {0}".format(self.objTypeEntry))
	
# pmgr Errors

class pmgrInitError(Error):
	"""Exception raised if a pmgr object could not be initialized."""
	def __init__(self, objType, hutch):
		self.objType = objType
		self.hutch = hutch
	def __str__(self):
		return repr("Failed to create pmgr object for objType: {0}, hutch: {1}.
".format(self.objType, self.hutch))

class pmgrKeyError(Error):
	"""Exception raised if a particular key is not in the pmgr."""
	def __init__(self, key):
		self.key = key
	def __str__(self):
		return repr("Key(s) {0}, not found in pmgr".format(self.key))
	
