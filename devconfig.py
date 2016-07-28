#!/usr/bin/python

import logging
import numpy as np

from pandas import DataFrame, Series, read_csv
from exceptionClasses import *
from pmgr.pmgrobj import pmgrobj
from difflib import get_close_matches
from optparse import OptionParser
from sys import exit
from os import system
from ConfigParser import SafeConfigParser
from ast import literal_eval
from collections import Iterable
from psp import Pv
from itertools import islice

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
		self._hutches         = []            #List of lists of hutches to use
		self._objTypes        = []            #List of lists of objtypes to use
		self._mode            = "pmgr"        #Mode for local behavior
		self._allMetaData     = DataFrame()   #DF of all the metadata
		self._allHutches      = set()         #Set of all valid hutches
		self._allObjTypes     = set()         #Set of all valid objTypes
		self._globalMode      = "pmgr"        #Default mode set 
		self._hutchAliases    = DataFrame()   #DF of hutch, aliases
		self._objTypeNames    = DataFrame()   #DF of hutch, objType, Names
		self._objTypeIDs      = DataFrame()   #DF of objType, IDs
		self._objTypeKeys     = DataFrame()   #DF of hutch, objType, keys
		self._savePreHooks    = DataFrame()   #DF of hutch, objType, sPrH
		self._savePostHooks   = DataFrame()   #DF of hutch, objType, sPoH
		self._applyPreHooks   = DataFrame()   #DF of hutch, objType, aPrH
		self._applyPostHooks  = DataFrame()   #DF of hutch, objType, aPoH
		self._verbosity       = DataFrame()   #DF of hutch, objType, verbosity
		self._logLevel        = DataFrame()   #DF of hutch, objType, logLevel
		self._loggingPath     = DataFrame()   #DF of hutch, objType, path
		self._zenity          = DataFrame()   #DF of hutch, objType, bool
		self._objTypeFldMaps  = {}            #Dict of objType:FldMapDF pairs
		self._aliases         = set()         #Set of all known aliases
		self._pmgr            = None          #Pmgr used for dcfg operations
		self._logger          = None          #devconfig logger
		# self._successfulInit  = False         #Attr to check if init was successful
		self._setAttrs()
		# try:
		# 	self._getAttrsPmgr()          #Looks up devconfig data in the pmgr
		# except LocalModeEnabled:
		# 	self._getAttrsLocal()
		self._initLogger()                #Setup the logger
		self._setInstanceAttrs(kwargs)    #Fills in instance attrs using inputs
		# self._setPmgr
		# self._cachedObjs      = {}          #Dict of (SN,objType,hutch):ObjFLD Dict
		# self._cachedCfgs      = {}          #Dict of (name,objType,hutch):cfgFLD Dict

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
		    self._setMode(kwargs["mode"])
		except (ValueError, KeyError):
			self._localMode = "pmgr"
			
	def _setHutches(self, inpHutches):
		"""Sets _hutches checking _hutchAliases and _allHutches."""
		if not isiterable(inpHutches):
			inpHutches = [[inpHutches]]
		elif not isiterable(inpHutches[0]):
			inpHutches = [inpHutches]
		validHutches, invalidHutches = [], []
		for hutches in inpHutches:
		    valid, invalid = self._getValidHutches(hutches)
		    validHutches.append(valid)
		    invalidHutches.append(invalid)
		if not validHutches:
			raise InvalidHutchError(inpHutches)
		elif invalidHutches:
			print "Invalid hutch entries '{0}', not included in hutch \
list".format(invalidHutches)
		self._hutches = validHutches

	def _getValidHutches(self, inpHutches):
		"""Returns a valid and invalid list of hutches given the inputted list.""" 
		hutches      = set(hutch.lower() for hutch in set(inpHutches))
		aliasesFound = set(a for a in hutches if a in self._aliases)
		for alias in aliasesFound:
			hutches.remove(alias)
			hutches.add(self._getValWhereTrue(self._hutchAliases, 'hutch',
			                                  'hutchAliases', alias))
		validHutches = hutches.intersection(self._allHutches)
		invalidHutches = hutches - self._allHutches
		return list(validHutches), list(invalidHutches)

	def _getValWhereTrue(self, DF, col1, col2, val):
		"""Return the values of col1 where col2 == val."""
		return DF.iloc[self._getIdxWhereTrue(DF, col2, val)][col1].tolist()

	def _getIdxWhereTrue(self, DF, col, val):
		"""Returns the row index where col == val."""
		if isinstance(val, basestring):
			boolSer = DF[col].str.contains(val)
			return boolSer[boolSer == True].index.tolist()

	def _getHutchObjTypeVal(self, DF, col, hutch, objType = None):
		if objType is not None:
		    return  DF[(DF.hutch==hutch) & (DF.objType==objType)][col].tolist()
		else:
		    return DF[DF.hutch==hutch][col].values.tolist()

	def _setObjTypes(self, inpObjTypes):
		"""Sets _objTypes checking _allObjTypes."""
		objTypes = {objType.lower() for objType in set(inpObjTypes)}
		validObjTypes = objTypes.intersection(self._allObjTypes)
		if not validObjTypes:
			raise InvalidObjTypeError(inpObjTypes)
		self._objTypes = validObjTypes

	def _setMode(self, mode):
		"""Sets mode. Takes pmgr or local."""
		if mode.lower() == "pmgr" or mode.lower() == "local":
		    self._mode = mode
		elif mode is None:
			pass
		else: 
			raise ValueError("Invalid input: '{0}'. Mode must be 'pmgr' or \
'local'".format(mode))

	def _setAttrs(self):
		"""
		Sets all the devconfig metadata from either the pmgr or the local DF.
		"""
		# # Uncomment this after devconfig has been added to the
		# self._allHutches.add('devconfig')
		# self._allObjTypes.add('devconfig')
		self._successfulInit = False
		try:
			if self._mode == "local": raise LocalModeEnabled
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
		except (pmgrInitError, InvalidHutchError, InvalidObjTypeError,
		        LocalModeEnabled):
			self._setAttrsLocal()
			
		self._getObjTypeFLDMaps()
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
		
	def _setAttrsLocal(self):
		"""
		Grabs as many devconfig pmgr-attributes from a local cfg file as it can.
		"""
		self._allMetaData     = self._readLocalCSV('db/localMode.csv')
		self._allHutches      = self._getSlice('hutch', outType = set)
		self._allObjTypes     = self._getSlice('objType', outType = set)
		self._globalMode      = self._getSlice('globalMode')
		self._hutchAliases    = self._getSlice('hutch', 'hutchAliases')
		self._objTypeNames    = self._getSlice('objTypeNames')
		self._objTypeIDs      = self._getSlice('objType', 'objTypeIDs')
		self._objTypeKeys     = self._getSlice('objTypeKeys')
		# When starting to port over the pmgr look at this again to see if this
		# is the right thing to do and if its even possible.
		self._savePreHooks    = self._getSlice('savePreHooks')
		self._savePostHooks   = self._getSlice('savePostHooks')
		self._applyPreHooks   = self._getSlice('applyPreHooks')
		self._applyPostHooks  = self._getSlice('applyPostHooks')
		# ----------------------------------------------------------------------
		self._verbosity       = self._getSlice('verbosity')
		self._logLevel        = self._getSlice('logLevel')
		self._loggingPath     = self._getSlice('loggingPath')
		self._zenity          = self._getSlice('zenity')
		self._aliases         = self._getAliases()

	def _readLocalCSV(self, csv, repNan = '', idxCol = None):
		"""
		Reads in a dataframe from the inputted localMode file path. A convenience 
		method to perform whatever preprocessing is necessary before using the 
		data.
		"""
		df = read_csv(csv, index_col = idxCol)
		df = df.fillna(repNan)
		for column in df.columns:
			if df[column].dtype == "O":
				if ( any(df[column].str.contains(r'\[\]')) or 
				     any(df[column].str.contains(r'\(\)'))):
					df[column] = df.column.apply(literal_eval)
		return df
	
	def _getSlice(self, *args, **kwargs):
		"""
		Looks at the allMetaData attr and grabs whichever column is inputted by
		name.
		
		Returns a dictionary of the hutchObjType to column value if if no outType
		is specified, a set of the column if outType is a set, and a list if it
		is set to list.
		"""
		outType = kwargs.get('outType', None)
		data    = kwargs.get('data', self._allMetaData)
		if outType is None:
			if len(args) == 1:
				cols = ["hutch", "objType"] + args
				return data[cols].drop_duplicates()
			elif len(args) == 2:
				return data[args].drop_duplicates().set_index(args[0])				
			else:
				return data[args].drop_duplicates()
		elif outType is set:
			if len(args) == 1:
				return set(data[args].tolist())
			else:
				raise ValueError("Can only take 1 column for type set.")
		else:
			raise TypeError("Invalid outType entry: '{0}'.".format(outType))

	def _getAliases(self):
		"""Returns a set of all the known aliases."""
		allAliases = self._hutchAliases.hutchAliases.values
		return set([alias for tupAlias in allAliases for alias in tupAlias])

	def _getObjTypeFLDMaps(self):
		"""Reads the fld_maps stored in the db folder."""
		try:
			for objType in self._allObjTypes:
				self._objTypeFldMaps[objType] = self.__readLocalCSV(
					"db/"+objType+".csv", repNan = [], idxCol = 0)
		except:
			print "Failed to read fldMaps."
			# Do more than just print for final rel

	def _initLogger(self):
		# Make sure to handle concurrent devconfig use
		pass

	def _listFieldsWith(self, objType, property, val):
		"""Return a list of fields which have their 'property' set to 'value'."""
		fldDict = self._objTypeFldMaps[objType]
		return fldDict[fldDict[property] == val].index.tolist()
	
	def _listObjFields(self, objType):
		"""Returns a list of obj fields."""
		return self._listFieldsWith(objType, 'obj', True)

	def _listCfgFields(self, objType):
		"""Returns a list of cfg fields."""
		return self._listFieldsWith(objType, 'obj', False)
		

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


	#############################################################################
	#                                   Diff                                    #
	#############################################################################
	
	def Diff(self, **kwargs):
		"""
		Method that prints the diffs between two different sources. Valid pairs
		are two live configs, a live and pmgr config, and two pmgr configs.
		"""
		self._setInstanceAttrs(kwargs)
		
		PVs = self._processKWArg(kwargs, "pv", None) 
		SNs = self._processKWArg(kwargs, "sn", None)
		# Check the PVs and SNs
		# Comparing 2 inputted pvs for diffs
		if len(PVs) == 2:
		    self._inferFromPVs(PVs)
		    fldMap   = self._objTypeFldMaps[objType[0]]
		    liveFlds = [self._getLiveFldDict(pv, objType) for pv, objType in 
		                zip(PVs, self._objTypes)]
		    diffDf   = self._getDiffDf(liveFlds, fldMap)
		    print diffDf.to_string(col_space = 10, index = False)
		else:
			raise NotImplementedError()

	def _proccessKWArg(self, kwargs, kw, defaultVal = None, outType = list):
		"""
		Processes a key word argument and performs any preprocessing necessary.
		"""
		arg = kwargs.get(kw, defaultVal)
		if isiterable(arg):
			return arg
		else:
			return outType(arg)

	def _inferFromPVs(self, PVs):
		if not self._hutches:
			for pv in PVs:
				hutches, _ = self._getValidHutches(pv[:3])
				if hutch:
				    self._hutches.append(hutches)
				else:
				    break
			# Porbably need to turn this into its own method
			if len(self._hutches) != len(PVs):
			    self._hutches = []
			    print "Could not infer hutch(es) from PV(s). Please enter hutch:"
			    for pv in PVs:
				    inpHutch = None
				    while not inpHutch:
					    inpHutch = input("{0} - ".format(pv))
					    if inpHutch not in self._allHutches:
						    print "Invalid hutch entry: '{0}'".format(inpHutch)
						    inpHutch = None
					self._hutches.append([inpHutch])

		if not self._objTypes:
			for pv, hutch in zip(PVs, self._hutches):
				# Yes I am a lazy sob
				if len(self._allObjTypes) == 1:
					self._objTypes.append(self._allObjTypes[0])
				else:
					# Fill this in at some point
					raise NotImplementedError()

	def _getLiveFldDict(self, PV, objType):
		"""Returns a dictionary of fields to values for the inputted PV."""
		fldDict   = {}
		fieldMap  = self._objTypeFldMaps[objType]
		objTypeID = self._objTypeIDs.loc[objType][objTypeIDs]
		for fld in fldMap.index:
			if fld == objTypeID:
				continue
			fldDict[fld] = Pv.get(PV + fldMap.loc[fld]['pv'])
			if fldMap.enum[fld]:
				try:
					fldDict[fld] = fldMap.enum[fld][fldDict[fld]]
				except IndexError:
					print "WARNING: index mismatch in field {0}.".format(fld) 
                    print "An ioc has been updated without updating the \
Parameter Manager!"
					fldDict[fld] = fldMap.enum[fld][0]
		return fldDict

	def _getDiffDf(self, fldDicts, fldMap):
		"""
		Returns a df with the alias, tooltip and values of the different fields.
		"""
		idxDiffs  = self._getDiffFlds(liveFlds)
		diffDicts = [{i:fldDict[i] for i in idxDiffs} for fldDict in fldDicts]
		diffDf    = fldMap.loc[idxDiffs][['alias', 'tooltip']].reset_index()
		for fldDict, diffDict in zip(fldDicts, diffDicts):
			diffDf[fldDicts["FLD_DESC"]] = diffDf['index'].map(diffDict)
		diffDf = diffDf.drop('index', 1)
		return diffDf

	def _getDiffFlds(self, fldDicts):
		"""Returns the names of the fields that are different."""
		diffFlds = []
		for fld in fldDicts[0].keys():
			val = fldDicts[0][fld]
			for fldDict in islice(fldDicts, 1, len(fldDicts)):
				if fldDict[fld] != val:
					diffFlds.append(fld)
		diffFlds = diffFlds.sort()
		return diffFlds
		
                    
	def Import(self):
		raise NotImplementedError()

	def Save(self):
		raise NotImplementedError()

	def Apply(self):
		raise NotImplementedError()

	def Revert(self):
		raise NotImplementedError()

	def Refresh(self, mode = None):
		"""Reinitializes the metadata using the pmgr or the csv."""
		self._setMode(local)
		self._setAttrs()
		# try:
		# 	self._getAttrsPmgr()
		# except LocalModeEnabled:
		# 	self._getAttrsLocal()





	#############################################################################
	#                              Property Methods                             #
	#############################################################################
	
	# These are all still written assuming dictionaries for the attributes, so
	# they need to be redone for DFs.
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

	# # Instance properties
	# @property
	# def hutches(self):
	# 	"""Returns a set of devconfig instance hutches."""
	# 	return self._hutches
	# @hutches.setter
	# def hutches(self, *args):
	# 	"""Sets the instance hutches to the inputted tuple/list/set."""
	# 	hutches = set()
	# 	for arg in args:
	# 		hutches = hutches.union(set(arg))
	# 	self._setHutches(hutches)

	# @property
	# def objTypes(self):
	# 	"""Returns a set of devconfig instance objTypes."""
	# 	return self._objTypes
	# @objTypes.setter
	# def objTypes(self, *args):
	# 	"""Sets the instance objTypes to the inputed tuple/list/set."""
	# 	objTypes = set()
	# 	for arg in args:
	# 		objTypes = objTypes.union(set(arg))
	# 	self._setObjTypes(objTypes)

	# @property
	# def mode(self):
	# 	"""Returns the mode devconfig is currently running in."""
	# 	return self._mode
	# @localMode.setter
	# def mode(self, mode):
	# 	"""Sets local mode to inputted mode (pmgr/local)."""
	# 	self._setMode(mode)

	# # Parameter manager fields. 
	# @property
	# def allHutches(self):
	# 	"""Returns a set of all hutches currently in the pmgr."""
	# 	return self._allHutches
	# @allHutches.setter
	# def allHutches(self, *args):
	# 	"""Cannot set _allHutches. Included to remove setting functionality."""
	# 	print "Cannot set allHutches"

	# @property
	# def allObjTypes(self, objTypes=set()):
	# 	"""Returns a set of all objTypes currently in the pmgr."""
	# 	return self._allObjTypes
	# @allObjTypes.setter
	# def allObjTypes(self, *args):
	# 	"""Cannot set _allObjTypes. Included to remove setting functionality."""
	# 	print "Cannot set allObjTypes"
		
	# # @property
	# # def hutchAliases(self, hutches=set()):
	# # 	# Will need to modify the set and return dict methods for hutch aliases
	# # 	# as the values are going to be sets.
	# # 	raise NotImplementedError()
	# # @hutchAliases.setter
	# # def hutchAliases(self, hutchAliasesDict):
	# # 	# Need to make sure that when setting aliases that all hutches are valid
	# # 	raise NotImplementedError()

	# @property
	# def objTypeNames(self, objTypes=set()):
	# 	"""Return the real-world names of the objTypes as objType:name dicts."""
	# 	return self._returnDict(self._objTypeNames, 
	# 	                        keys      = objTypes,
	# 	                        validKeys = self._hutchObjType)
	# @objTypeNames.setter
	# def objTypeNames(self, objTypeNamesDict):
	# 	"""
	# 	Sets the objType names of the inputted objType(s) to that specified in
	# 	the dict.
	# 	"""
	# 	self._updateDict(self._objTypeNames, objTypeNamesDict,
	# 					 validKeys = self._hutchObjType)

	# @property
	# def objTypeIDs(self, objTypes=set()):
	# 	"""Returns the objType identifying field."""
	# 	return self._returnDict(self._objTypeIDs, 
	# 	                       keys      = objTypes,
	# 	                       validKeys = self._hutchObjType)
	# @objTypeIDs.setter
	# def objTypeIDs(self, *args):
	# 	"""This is included for the purpose of making it unavailable."""
	# 	# Raise some form of invalid setting error
	# 	print "Cannot set objType IDs - critical to devconfig functionality."

	# @property
	# def savePreHooks(self, objTypes=set()):
	# 	"""
	# 	Returns the path to the functions used as the savePreHook for each
	# 	objType.
	# 	"""
	# 	return self._returnDict(self._savePreHooks, 
	# 	                       keys      = objTypes,
	# 	                       validKeys = self._hutchObjType)
	# @savePreHooks.setter
	# def savePreHooks(self, savePreHooksDict):
	# 	pass
	# 	"""
	# 	Sets the path to the functions used as the savePreHooks for an objType.
	# 	"""
	# 	self._updateDict(self._savePreHooks, savePreHooksDict,
	# 					 validKeys = self._hutchObjType)

	# @property
	# def savePostHooks(self, objTypes=set()):
	# 	"""
	# 	Returns the path to the functions used as the savePostHook for each
	# 	objType.
	# 	"""
	# 	return self._returnDict(self._savePostHooks, 
	# 	                       keys      = objTypes,
	# 	                       validKeys = self._hutchObjType)
	# @savePostHooks.setter
	# def savePostHooks(self, savePostHooksDict):
	# 	"""
	# 	Sets the path to the functions used as the savePostHooks for an objType.
	# 	"""
	# 	self._updateDict(self._savePostHooks, savePostHooksDict,
	# 					 validKeys = self._hutchObjType)

	# @property
	# def applyPreHooks(self, objTypes=set()):
	# 	"""
	# 	Returns the path to the functions used as the applyPreHook for each
	# 	objType.
	# 	"""
	# 	return self._returnDict(self._applyPreHooks, 
	# 	                       keys      = objTypes,
	# 	                       validKeys = self._hutchObjType)
	# @applyPreHooks.setter
	# def applyPreHooks(self, applyPreHooksDict):
	# 	"""
	# 	Sets the path to the functions used as the applyPreHooks for an objType.
	# 	"""
	# 	self._updateDict(self._applyPreHooks, applyPreHooksDict,
	# 					 validKeys = self._hutchObjType)

	# @property
	# def applyPostHooks(self, objTypes=set()):
	# 	"""
	# 	Returns the path to the functions used as the applyPostHook for each
	# 	objType.
	# 	"""
	# 	return self._returnDict(self._applyPostHooks, 
	# 	                       keys      = objTypes,
	# 	                       validKeys = self._hutchObjType)
	# @applyPostHooks.setter
	# def applyPostHooks(self, applyPostHooksDict):
	# 	"""
	# 	Sets the path to the functions used as the applyPostHooks for an objType.
	# 	"""
	# 	self._updateDict(self._applyPostHooks, applyPostHooksDict,
	# 					 validKeys = self._hutchObjType)

	# @property
	# def verbosity(self, hutches=set()):
	# 	"""
	# 	Returns a dictionary of the verbosity level set for the inputted 
	# 	hutch(es). Returns all of them if none is specified.
	# 	"""
	# 	return self._returnDict(self._verbosity, 
	# 	                       keys      = hutches,
	# 	                       validKeys = self._hutchObjType)

	# @verbosity.setter
	# def verbosity(self, verbosityDict):
	# 	"""
	# 	Sets the verbosity level of the hutch(es) to that specified in the 
	# 	inputted {hutch:level} dictionary.
	# 	"""
	# 	self._updateDict(self._verbosity, verbosityDict, 
	# 					 validKeys = self._hutchObjType, 
	# 					 validVals = self._validLogLevels)

	# @property
	# def logLevel(self, hutches=set()):
	# 	"""
	# 	Returns a dictionary of the logLevel level set for the inputted 
	# 	hutch(es). Returns all of them if none is specified.
	# 	"""
	# 	return self._returnDict(self._logLevel, 
	# 	                       keys      = hutches,
	# 	                       validKeys = self._hutchObjType)

	# @logLevel.setter
	# def logLevel(self, logLevelDict):
	# 	"""
	# 	Sets the logLevel level of the hutch(es) to that specified in the 
	# 	inputted {hutch:level} dictionary.
	# 	"""
	# 	self._updateDict(self._logLevel, logLevelDict, 
	# 					 validKeys = self._hutchObjType, 
	# 					 validVals = self._validLogLevels)

def isiterable(obj):
	"""
	Function that determines if an object is an iterable, but not including 
	strings.
	"""
	if isinstance(obj, basestring):
		return False
	else:
		return isinstance(obj, Iterable)

def flatten(inpIter):
	"""Recursively iterate through values in nested iterables."""
	for val in inpIter:
		if isiterable(val):
			for inVal in flatten(val):
				yield inVal
		else:
			yield val

def isempty(seq):
	"""Checks if an iterable (nested or not) is empty."""
	return not any(1 for _ in flatten(seq))
		
#################################################################################
#                             Stand Alone Routines                              #
#################################################################################

# def diff(*args):74
# 	dCfg = 


if __name__ == "__main__":
	dCfg = devconfig()
