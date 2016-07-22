#!/usr/bin/python

import logging
import numpy as np
import pandas as pd

from exceptionClasses import *
from pmgr.pmgrobj import pmgrobj
from difflib import get_close_matches
from optparse import OptionParser
from sys import exit
from os import system
from ConfigParser import SafeConfigParser
from ast import literal_eval

class devconfig(object):
	"""
	Main devconfig class that interfaces with the pmgr

	Methods:
	.Gui()              Launches the pmgr gui for the given hutch and objType
	.View()             Shows device info from the pmgr
	.Search()           Searches the pmgr for the inputted obj/cfg/hutch/objType
	.New()              Add new objs/cfgs/hutch/objtypes to pmgr
	.Edit()             Edit existing objs/cfgs/hutch/objtypes
	.Diff()             Return diffs between inputted PVs, or PV and pmgr entry
	.Import()           Import cfg dict to pmgr
	.Save()             Save obj/cfg to pmgr
	.Apply()            Apply pmgr values to device
	.Update()           Search for updates, and/or update devconfig pmgr entries
	"""
	def __init__(self, **kwargs):
		# All meta data should be fetched from the pmgr
		# For now assume singular objType: ims_motor
		self._hutches        = set()      #List of hutches to use in methods
		self._objTypes       = set()      #List of objTypes to use in methods
		self._localMode      = False      #Run devconfig in local mode
		self._allMetaData    = None       #Pd df initialized if loading from df
		self._hutchObjType   = []         #List of (hutch,objType) tuples
		self._allHutches     = set()      #List of all valid hutches
		self._allObjTypes    = set()      #List of all valid objTypes
		self._hutchAliases   = {}         #Dict of hutch:(aliases) pairs
		self._objTypeNames   = {}         #Dict of objtype:device name pairs
		self._objTypeIDs     = {}         #Dict of objType:Identifying FLD pairs
		self._savePreHooks   = {}         #Dict of save objtype:prehook pairs
		self._savePostHooks  = {}         #Dict of save objtype:posthook pairs
		self._applyPreHooks  = {}         #Dict of apply objtype:prehook pairs
		self._applyPostHooks = {}         #Dict of apply objtype:posthook pairs
		self._verbosity      = {}         #Dict of hutch:verbosity level pairs
		self._logLevel       = {}         #Dict of hutch:logging level pairs
		self._loggingPath    = {}         #Dict of hutch:logging path pairs
		self._validLogLevels = set()      #Set of the valid logging levels
		self._aliases        = set()      #Set of all known aliases
		self._logger         = None       #devconfig logger
		self._zenity         = {}         #Dict of hutch:T/F for zenity popups
		self._pmgr           = None       #Pmgr Obj used for devconfig operations
		self._successfulInit = False      #Attr to check if init was successful
		self._cachedObjs     = {}         #Dict of (SN,objType,hutch):ObjFLD Dict
		self._cachedCfgs     = {}         #Dict of (name,objType,hutch):cfgFLD Dict
		try:
			self._getAttrsPmgr()          #Looks up devconfig data in the pmgr
		except LocalModeEnabled:
			self._getAttrsLocal()
		self._initLogger()                #Setup the logger
		self._setInstanceAttrs(kwargs)    #Fills in instance attrs using inputs


	#############################################################################
	#                           Initialization Methods                          #
	#############################################################################	

	def _setInstanceAttrs(self, kwargs):
		"""Fills in the instance attributes using the inputted kw arguments."""
		if "hutches" in kwargs.keys():
			self._setHutches(kwargs["hutches"])
		if "objTypes" in kwargs.keys():
			self._setObjTypes(kwargs["objTypes"])
		try:
		    self._setLocalMode(kwargs["localMode"])
		except (ValueError, KeyError):
			self._localMode = False
			
	def _setHutches(self, inpHutches):
		"""Sets _hutches checking _hutchAliases and _allHutches."""
		hutches = {hutch.lower() for hutch in set(inpHutches)}
		aliasesFound = {a for a in hutches if a in self._aliases}
		for alias in aliasesFound:
			hutches.remove(alias)
			hutches = hutches.union(self._getHutchesFromAlias(alias))
		validHutches = hutches.intersection(self._allHutches)
		if not validHutches:
			raise InvalidHutchError(inpHutches)
		self._hutches = validHutches
		
	def _getHutchesFromAlias(self, alias):
		"""Returns the hutches to substitute for the alias inputted."""
		hutchToAliases = self._hutchAliases
		hutches        = set()
		for hutch in hutchToAliases:
			if alias in hutchToAliases[hutch]:
				hutches.add(hutch[0])
		return hutches
	
	def _setObjTypes(self, inpObjTypes):
		"""Sets _objTypes checking _allObjTypes."""
		objTypes = {objType.lower() for objType in set(inpObjTypes)}
		validObjTypes = objTypes.intersection(self._allObjTypes)
		if not validObjTypes:
			raise InvalidObjTypeError(inpObjTypes)
		self._objTypes = validObjTypes

	def _setLocalMode(self, mode):
		"""Sets local mode. Takes True or False"""
		if isinstance(mode, bool):
		    self._localMode = mode
		else: 
			raise ValueError("Invalid input: '{0}'. Mode must be True or \
False".format(mode))

	def _getAttrsPmgr(self):
		"""Grabs all the devconfig data from the devconfig pmgr entries."""
		# # Uncomment this after devconfig has been added to the
		# self._allHutches.add('devconfig')
		# self._allObjTypes.add('devconfig')
		self._successfulInit = False
		if self._localMode: raise LocalModeEnabled
		try:
			# Adding new object types doesnt seem particularly easy, and not only
			# from a technical point of view.
			
			# The sql server also hosts the databases for the elog, exp files and 
			# other essential beamline databases, so adding entries needs some 
			# level of supervision. And even if adding values is scriptified,
			# there isnt a universal way to check for safety on the inputs.

			# Perhaps what could be done is having add be more of a request,
			# where someone specifies the parameters they want and then an email
			# gets sent out to someone (me or Mike) to review the entries before
			# approving.

			# As for actually adding objtypes, the bulk of it is in creating the
			# various .sql files in the /DB directory of the pmgr. Look there for
			# the structure behind the ims_motor objtype to add new ones. After
			# that, mysql commands have to be executed to actually add the new 
			# files to the pmgr.
			self._pmgr = self._getPmgr('devconfig', 'devconfig')
			# ...
			# Load everything from the pmgr
			# ...
			self._successfulInit = True
		except (pmgrInitError, InvalidHutchError, InvalidObjTypeError):
			self._getAttrsLocal()
			self._successfulInit = True
			
	def _getPmgr(self, objType, hutch):
		"""
		Returns a pmgr object with the inputted objType and hutch. Because only
		one pmgrObj can be used at a time, entries for objType and hutch must be
		a single objType and hutch, not multiple.
		"""
		if not isinstance(objType, str) or not isinstance(hutch, str):
			raise typeError('str')
		if objType.lower() not in self._allObjTypes:
			raise InvalidObjTypeError(objType)
		if hutch.lower() not in self._allHutches:
			raise InvalidHutchError(hutch)
		try:
			pmgr = pmgrobj(objType.lower(), hutch.lower())
			pmgr.updateTables()
		except:
			raise pmgrInitError(objType, hutch)
		return pmgr
		
	def _getAttrsLocal(self):
		"""
		Grabs as many devconfig pmgr-attributes from a local cfg file as it can.
		"""
		self._allMetaData     = self._readLocalCSV('localMode.csv')  #Maybe make this a real path
		self._hutchObjType    = self._getData('HutchesObjTypes', list)
		self._allHutches      = self._getData('HutchesObjTypes', set, 0)
		self._allObjTypes     = self._getData('HutchesObjTypes', set, 1)
		self._hutchAliases    = self._getData('hutchAliases')
		self._objTypeNames    = self._getData('objTypeNames')
		self._objTypeIDs      = self._getData('objTypeIDs')
		# When starting to port over the pmgr look at this again to see if this
		# is the right thing to do and if its even possible.
		self._savePreHooks    = self._getData('savePreHooks')
		self._savePostHooks   = self._getData('savePostHooks')
		self._applyPreHooks   = self._getData('applyPreHooks')
		self._applyPostHooks  = self._getData('applyPostHooks')

		self._verbosity       = self._getData('verbosity')
		self._logLevel        = self._getData('logLevel')
		self._loggingPath     = self._getData('loggingPath')
		self._zenity          = self._getData('zenity')
		self._aliases         = self._getAliases()
		self._validLogLevels  = {"DEBUG","INFO","WARNING","ERROR","CRITICAL"}

	def _readLocalCSV(self, csv):
		"""
		Reads in a dataframe from the inputted localMode file path. A convenience 
		method to perform whatever preprocessing is necessary before using the 
		data.
		"""
		df = pd.read_csv(csv)
		df.HutchesObjTypes = df.HutchesObjTypes.apply(literal_eval)
		df.hutchAliases    = df.hutchAliases.apply(literal_eval)
		df                 = df.replace(np.nan,'', regex=True)
		return df
	
	def _getData(self, name, outType=dict, index=None, key='HutchesObjTypes'):
		"""
		Looks at the allMetaData attr and grabs whichever column is inputted by
		name.
		
		Returns a dictionary of the hutchObjType to column value if if no outType
		is specified, a set of the column if outType is a set, and a list if it
		is set to list.
		"""
		data    = self._allMetaData
		if outType is list:
			if index is None:
				return data[name].tolist()
			else:
				return data[name].tolist()[index]
		elif outType is set:
			if index is None:
				return set(data[name].tolist())
			else:
				return set(zip(*data[name].tolist())[index])
		elif outType is dict:
			return pd.Series(
				data[name].values, index = data.HutchesObjTypes).to_dict()
		else:
			raise TypeError("outType must be list, set or dict.")		

	def _getAliases(self):
		"""Returns a set of all the known aliases."""
		allAliases = self._hutchAliases.values()
		return set([alias for tupAlias in allAliases for alias in tupAlias])

	def _initLogger(self):
		# Make sure to handle concurrent devconfig use
		pass

	#############################################################################
	#                          Outward Facing Methods                           #
	#############################################################################

	def Gui(self, **kwargs):
		"""
		Launches the parameter manager gui for specified hutch and objType. Will
		ask for hutch or objType if they are not provided.
		"""
		raise NotImplementedError()
		# Not working yet
		# validHutches = set()
		# if "hutches" in kwargs.keys():		
		# 	validHutches = set(kwargs["hutches"]).intersection(self._allHutches)
			
		# if "hutches" in kwargs.keys():
		# 	self._hutches = set(kwargs["hutches"]).intersection(self._allHutches)
		# elif "hutches" in kwargs.keys() and not set(
		# 		kwargs["hutches"]).intersection(self._allHutches): 
		# 	print "Invalid hutch entry"

	def View(self, ID):
		raise NotImplementedError()

	def Search(self):
		raise NotImplementedError()

	def New(self):
		raise NotImplementedError()
	
	def Edit(self):
		raise NotImplementedError()

	def Diff(self):
		raise NotImplementedError()

	def Import(self):
		raise NotImplementedError()

	def Save(self):
		raise NotImplementedError()

	def Apply(self):
		raise NotImplementedError()

	def Revert(self):
		raise NotImplementedError()

	def Refresh(self, local = None):
		"""Reinitializes the metadata using the pmgr or the csv."""
		if local is not None and isinstance(local, bool):
			self._localMode = local
		try:
			self._getAttrsPmgr()
		except LocalModeEnabled:
			self._getAttrsLocal()

	#############################################################################
	#                              Property Methods                             #
	#############################################################################
	
	def _returnDict(self, attr, **kwargs):
		"""Returns attrDict of the attr."""
		keys      = set(kwargs.get("keys", set()))
		validKeys = set(kwargs.get("validKeys", set()))
		if not keys:
			return attr
		elif not validKeys:
			return {key:attr[key] for key in keys}
		elif not keys.intersection(validKeys):
			raise pmgrKeyError(keys)
		else:
			return {key:attr[key] for key in keys.intersection(validKeys)}

	def _updateDict(self, attr, attrDict, **kwargs):
		"""Updates the attr using the attrDict"""
		if not isinstance(attr, dict) or not isinstance(attrDict, dict):
			raise typeError('dict')
		validKeys = set(kwargs.get("validKeys", set()))
		validVals = set(kwargs.get("validVals", set()))
		for key in attrDict.keys():
			if validKeys:
				if key not in validKeys:
					print "Invalid key entry: '{0}'. Skipping.".format(key)
					continue
			if validVals:
				if attrDict[key] not in validVals:
					print "Invalid val entry: '{0}'. Skipping.".format(
						attrDict[key])
					continue
			attr[key] = attrDict[key]

	#############################################################################
	#                            devconfig Properties                           #
	#############################################################################

	# Instance properties
	@property
	def hutches(self):
		"""Returns a set of devconfig instance hutches."""
		return self._hutches
	@hutches.setter
	def hutches(self, *args):
		"""Sets the instance hutches to the inputted tuple/list/set."""
		hutches = set()
		for arg in args:
			hutches = hutches.union(set(arg))
		self._setHutches(hutches)

	@property
	def objTypes(self):
		"""Returns a set of devconfig instance objTypes."""
		return self._objTypes
	@objTypes.setter
	def objTypes(self, *args):
		"""Sets the instance objTypes to the inputed tuple/list/set."""
		objTypes = set()
		for arg in args:
			objTypes = objTypes.union(set(arg))
		self._setObjTypes(objTypes)

	@property
	def localMode(self):
		"""Returns whether devconfig instance is in localMode."""
		return self._localMode
	@localMode.setter
	def localMode(self, mode):
		"""Sets local mode to inputted mode (True/False)."""
		self._setLocalMode(mode)

	# Parameter manager fields. 
	@property
	def allHutches(self):
		"""Returns a set of all hutches currently in the pmgr."""
		return self._allHutches
	@allHutches.setter
	def allHutches(self, *args):
		"""Cannot set _allHutches. Included to remove setting functionality."""
		print "Cannot set allHutches"

	@property
	def allObjTypes(self, objTypes=set()):
		"""Returns a set of all objTypes currently in the pmgr."""
		return self._allObjTypes
	@allObjTypes.setter
	def allObjTypes(self, *args):
		"""Cannot set _allObjTypes. Included to remove setting functionality."""
		print "Cannot set allObjTypes"
		
	# @property
	# def hutchAliases(self, hutches=set()):
	# 	# Will need to modify the set and return dict methods for hutch aliases
	# 	# as the values are going to be sets.
	# 	raise NotImplementedError()
	# @hutchAliases.setter
	# def hutchAliases(self, hutchAliasesDict):
	# 	# Need to make sure that when setting aliases that all hutches are valid
	# 	raise NotImplementedError()

	@property
	def objTypeNames(self, objTypes=set()):
		"""Return the real-world names of the objTypes as objType:name dicts."""
		return self._returnDict(self._objTypeNames, 
		                        keys      = objTypes,
		                        validKeys = self._hutchObjType)
	@objTypeNames.setter
	def objTypeNames(self, objTypeNamesDict):
		"""
		Sets the objType names of the inputted objType(s) to that specified in
		the dict.
		"""
		self._updateDict(self._objTypeNames, objTypeNamesDict,
						 validKeys = self._hutchObjType)

	@property
	def objTypeIDs(self, objTypes=set()):
		"""Returns the objType identifying field."""
		return self._returnDict(self._objTypeIDs, 
		                       keys      = objTypes,
		                       validKeys = self._hutchObjType)
	@objTypeIDs.setter
	def objTypeIDs(self, *args):
		"""This is included for the purpose of making it unavailable."""
		# Raise some form of invalid setting error
		print "Cannot set objType IDs - critical to devconfig functionality."

	@property
	def savePreHooks(self, objTypes=set()):
		"""
		Returns the path to the functions used as the savePreHook for each
		objType.
		"""
		return self._returnDict(self._savePreHooks, 
		                       keys      = objTypes,
		                       validKeys = self._hutchObjType)
	@savePreHooks.setter
	def savePreHooks(self, savePreHooksDict):
		pass
		"""
		Sets the path to the functions used as the savePreHooks for an objType.
		"""
		self._updateDict(self._savePreHooks, savePreHooksDict,
						 validKeys = self._hutchObjType)

	@property
	def savePostHooks(self, objTypes=set()):
		"""
		Returns the path to the functions used as the savePostHook for each
		objType.
		"""
		return self._returnDict(self._savePostHooks, 
		                       keys      = objTypes,
		                       validKeys = self._hutchObjType)
	@savePostHooks.setter
	def savePostHooks(self, savePostHooksDict):
		"""
		Sets the path to the functions used as the savePostHooks for an objType.
		"""
		self._updateDict(self._savePostHooks, savePostHooksDict,
						 validKeys = self._hutchObjType)

	@property
	def applyPreHooks(self, objTypes=set()):
		"""
		Returns the path to the functions used as the applyPreHook for each
		objType.
		"""
		return self._returnDict(self._applyPreHooks, 
		                       keys      = objTypes,
		                       validKeys = self._hutchObjType)
	@applyPreHooks.setter
	def applyPreHooks(self, applyPreHooksDict):
		"""
		Sets the path to the functions used as the applyPreHooks for an objType.
		"""
		self._updateDict(self._applyPreHooks, applyPreHooksDict,
						 validKeys = self._hutchObjType)

	@property
	def applyPostHooks(self, objTypes=set()):
		"""
		Returns the path to the functions used as the applyPostHook for each
		objType.
		"""
		return self._returnDict(self._applyPostHooks, 
		                       keys      = objTypes,
		                       validKeys = self._hutchObjType)
	@applyPostHooks.setter
	def applyPostHooks(self, applyPostHooksDict):
		"""
		Sets the path to the functions used as the applyPostHooks for an objType.
		"""
		self._updateDict(self._applyPostHooks, applyPostHooksDict,
						 validKeys = self._hutchObjType)

	@property
	def verbosity(self, hutches=set()):
		"""
		Returns a dictionary of the verbosity level set for the inputted 
		hutch(es). Returns all of them if none is specified.
		"""
		return self._returnDict(self._verbosity, 
		                       keys      = hutches,
		                       validKeys = self._hutchObjType)

	@verbosity.setter
	def verbosity(self, verbosityDict):
		"""
		Sets the verbosity level of the hutch(es) to that specified in the 
		inputted {hutch:level} dictionary.
		"""
		self._updateDict(self._verbosity, verbosityDict, 
						 validKeys = self._hutchObjType, 
						 validVals = self._validLogLevels)

	@property
	def logLevel(self, hutches=set()):
		"""
		Returns a dictionary of the logLevel level set for the inputted 
		hutch(es). Returns all of them if none is specified.
		"""
		return self._returnDict(self._logLevel, 
		                       keys      = hutches,
		                       validKeys = self._hutchObjType)

	@logLevel.setter
	def logLevel(self, logLevelDict):
		"""
		Sets the logLevel level of the hutch(es) to that specified in the 
		inputted {hutch:level} dictionary.
		"""
		self._updateDict(self._logLevel, logLevelDict, 
						 validKeys = self._hutchObjType, 
						 validVals = self._validLogLevels)





#################################################################################
#                             Stand Alone Routines                              #
#################################################################################

# def diff(*args):74
# 	dCfg = 


if __name__ == "__main__":
	dCfg = devconfig()
