#!/usr/bin/python

import logging
import numpy as np
# from sys import exit
# from difflib import get_close_matches
from os import path, getcwd
from pandas import DataFrame, Series, read_csv
from exceptionClasses import *
from pmgr.pmgrobj import pmgrobj
from optparse import OptionParser
from ConfigParser import SafeConfigParser
from ast import literal_eval
from collections import Iterable
from psp.Pv import get
from itertools import islice
from pyca import pyexc

from pprint import pprint

directory = path.realpath(path.join(getcwd(), path.dirname(__file__)))

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
		self._objTypeNames    = DataFrame()   #DF of objType, Names
		self._objTypeIDs      = DataFrame()   #DF of objType, IDs
		self._objTypeKeys     = DataFrame()   #DF of hutch, objType, keys
		self._objTypeSumFlds  = DataFrame()
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
		if "hutches" in kwargs.keys() and kwargs["hutches"]:
			self._setHutches(kwargs["hutches"])
		if "objTypes" in kwargs.keys() and kwargs["objTypes"]:
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
		if not isiterable(inpHutches):
			inpHutches = set([inpHutches])
		hutches      = set(hutch.lower() for hutch in inpHutches)
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
		val = DF.loc[self._getIdxWhereTrue(DF, col2, val)][col1]
		if len(val.tolist()) > 1:
			return val.tolist()
		else:
			return ''.join(str(v) for v in val)

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
		if mode is None:
			pass
		elif mode.lower() == "pmgr" or mode.lower() == "local":
		    self._mode = mode
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
		if not isinstance(objType,basestring) or not isinstance(hutch,basestring):
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
		self._objTypeNames    = self._getSlice('objType', 'objTypeNames')
		self._objTypeIDs      = self._getSlice('objType', 'objTypeIDs')
		self._objTypeKeys     = self._getSlice('objTypeKeys')
		self._objTypeSumFlds  = self._getSlice('objType', 'objTypeSumFlds')
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
		df = read_csv(directory + "/" + csv, index_col = idxCol)
		df = df.fillna(repNan)
		for column in df.columns:
			if df[column].dtype == "O":
				if (any(df[column].str.contains(r'\[\]')) or 
				    any(df[column].str.contains(r'\(\)'))):
					try:
						df[column] = df[column].apply(literal_eval)
					except ValueError:
						# Figure this out
						pass
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
		args = list(args)
		if outType is None:
			if len(args) == 1:
				cols = ["hutch", "objType"] + args
				return data[cols].drop_duplicates()
			elif len(args) == 2:
				return data[args].drop_duplicates()			
			else:
				return data[args].drop_duplicates()
		elif outType is set:
			if len(args) == 1:
				return set(flatten(data[args].values.T.tolist()))
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
				self._objTypeFldMaps[objType] = self._readLocalCSV(
					"db/"+objType+".csv", repNan = "[]", idxCol = 0)
		except :
			print "Failed to read fldMaps."
		# 	print 
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
		
	#############################################################################
	#                                    Gui                                    #
	#############################################################################

	def Gui(self, *args, **kwargs):
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

	#############################################################################
	#                                  Search                                   #
	#############################################################################

	def Search(self, *args, **kwargs):
		raise NotImplementedError()

	def _search(self, *args, **kwargs):
		
		raise NotImplementedError()

	def _getObjWithID(self, devID, fldID):
		"""
		Returns the obj ID of the device using the device ID. Returns None if 
		no entry was found.
		"""
		pmgr  = self._pmgr
		devID = str(devID)
		pmgr.updateTables()
		for objID in pmgr.objs.keys():
			if devID == pmgr.objs[objID][fldID]:
				return objID
		return None

	#############################################################################
	#                                   View                                    #
	#############################################################################

	def View(self, *args, **kwargs):
		"""
		Prints a dataframe containing the pertinent information about a device
		inputted by PV or SN. Will return a search if the inputs could not be 
		found.
		"""
		self._setInstanceAttrs(kwargs)
		summary  = kwargs.get("summary", False)
		tooltip  = kwargs.get("tooltip", True)
		Pvs, IDs = self._inferFromArgs(args)
		self._inferFromPvs(Pvs)
		fldMap   = self._objTypeFldMaps[self._objTypes[0]]   #Check if this is okay
		devName  = self._getValWhereTrue(self._objTypeNames, "objTypeNames",
		                                "objType", self._objTypes[0])
		numPvs, numIDs = len(Pvs), len(IDs)

		# Assumptions for now
		# - The Entries definitely exist as a pv or a pmgr entry

		liveFlds = [self._getLiveFldDict(Pv, objtype) for Pv, objtype in zip(
			Pvs, self._objTypes)]
		pmgrFlds = [self._getPmgrFldDict(Pv, objType, hutch) for Pv, objType, 
		            hutch in zip(Pvs, self._objTypes, flatten(self._hutches))]


		liveDfs  = [self._getLiveViewDf(Pv, liveFld, objType, hutch, summary) 
		            for Pv, liveFld, objtype, hutch in zip(
			            Pvs, liveFlds, self._objTypes, flatten(self._hutches))]


	def _getLiveFldDict(self, Pv, objType):
		"""Returns a dictionary of fields to values for the inputted PV."""
		noConStr  = "NO CON"
		fldDict   = {}
		fldMap    = self._objTypeFldMaps[objType]
		objTypeID = self._getValWhereTrue(self._objTypeIDs, 'objTypeIDs', 
		                                  'objType', objType)
		for fld in fldMap.index:
			try:
				fldDict[fld] = str(get(Pv + fldMap.loc[fld]['pv']))
				if fldMap.enum[fld]:
					try:
						fldDict[fld] = str(fldMap.enum[fld][int(fldDict[fld])])
					except IndexError:
						print "WARNING: index mismatch in field {0}.".format(fld) 
						print "An ioc has been updated without updating the \
Parameter Manager!"
						fldDict[fld] = fldMap.enum[fld][0]
			except pyexc:
				print "Could not connect to '{0}'. Setting to '{1}'.".format(
					Pv + fldMap.loc[fld]['pv'], noConStr)
				fldDict[fld] = noConStr
		return fldDict

	def _getLiveViewDf(self, Pv, fldDict, objType, summary = False):
		"""
		Returns a dataframe containing the live values of the inputted device.
		"""
		self._pmgr  = self._getPmgr(objType, hutch)
		self._pmgr.updateTables()
		summaryFlds = self._objTypeSumFlds[objType]
		fldMap      = self._objTypeFldMaps[objType]
		fldID       = self._getValWhereTrue(self._objTypeIDs, 'objTypeIDs', 
		                               'objType', objType)		
		if summary:
			liveDf = fldMap.loc[summaryFlds][['alias', 'tooltip']].reset_index()
		else:
			liveDf = fldMap[['alias', 'tooltip']].reset_index()
		objID  = self._getObjWithID(fldDict[fldID]. fldID)
		pmgrDf = self._getPmgrDevSum(objID)
		viewDf = pd.concat(liveDf, pmgrDf)
		return viewDf

	def _getPmgrDevSum(self, objID):
		if not objID:
			inPmgr, objName, cfgName, lastMod = "No", "N/A", "N/A", "N/A"
		else:
			inPmgr  = "Yes"
			objName = self._pmgr.objs[objID]["name"]
			cfgID   = self._pmgr.objs[objID]["config"]
			cfgName = self._pmgr.cfgs[cfgID]["name"]
			objDateMod = self._pmgr.objs[objID]['dt_updated']
			cfgDateMod = self._pmgr.cfgs[cfgID]['dt_updated']
			if objDateMod > cfgDateMod:
				lastMod = objDateMod
			else:
				lastMod = cfgDateMod
		pmgrInfo = [("Pmgr Entry", "Is this device in pmgr", inPmgr), 
		            ("  Obj Name", "Pmgr object name", objName),
		            ("  Cfg Name", "Pmgr config name", cfgName),
		            ("  Last Modified", "Date of last entry modification",
		             lastMod)]
		return pd.DataFrame(pmgrInfo)
		
			



	def _view(self, df, nameIndexCols, **kwargs):
		"""
		Generalized view routine which returns a printable string version of the
		inputted dataframe.
		"""
		minColLen = kwargs.get("minColLen", 10)
		offSet    = kwargs.get("offSet", 0)
		lenCols   = kwargs.get("lenCols", [])
		if not lenCols or len(lenCols) != len(nameIndexCols):
			for i, name in enumerate(nameIndexCols):
				if not i:
					lenCols.append(df[df.columns[i]].str.len().max() + offSet)
				else:
					lenCols.append(df[df.columns[i]].str.len().max())
				
		for i in range(len(nameIndexCols), df.shape[1]):
			maxLenCol = df.iloc[:,i].astype(basestring).str.len().max()
			if maxLenCol > minColLen:
				lenCols.append(int(maxLenCol + offSet))
			else:
				lenCols.append(int(minColLen))
		headerStr = "\n "
		# print nameIndexCols
		for i, name in enumerate(df.columns):
			if i < len(nameIndexCols):
				headerStr += "{:<{}s}".format(nameIndexCols[i], lenCols[i])
				if i < len(nameIndexCols) - 1:
					headerStr += " " * (offSet + 1)
			else:
				# headerStr += " " * (offSet + 1)
				headerStr += "{:>{}s}".format(name, lenCols[i])

		lenRow = len(headerStr)
		print lenRow
		viewStr     = "-" * lenRow + headerStr + "\n" + "-" * lenRow + "\n"
		dfFormatter = {df.columns[i]:'{{:<{}s}}'.format(lenCol).format for i, 
		               lenCol in enumerate(lenCols[:len(nameIndexCols)])}
		dfStr       = df.to_string(index = False, formatters = dfFormatter)
		viewStr    += dfStr[lenRow:] + "\n" + "-" * lenRow + "\n"
		return viewStr

	#############################################################################
	#                                    Diff                                   #
	#############################################################################
	
	def Diff(self, *args, **kwargs):
		"""
		Method that prints the diffs between two different sources. Valid pairs
		are two live configs, a live and pmgr config, and two pmgr configs.
		"""
		self._setInstanceAttrs(kwargs)
		checkPmgr = kwargs.get("pmgr", False)
		tooltip   = kwargs.get("tooltip", False)
		minColLen = kwargs.get("minColLen", 14)
		offSet    = kwargs.get("offSet", 0)
		Pvs, IDs  = self._inferFromArgs(args)
		self._inferFromPvs(Pvs)
		fldMap  = self._objTypeFldMaps[self._objTypes[0]]   #Check if this is okay
		devName = self._getValWhereTrue(self._objTypeNames, "objTypeNames",
		                                "objType", self._objTypes[0])
		numPvs, numIDs = len(Pvs), len(IDs)
		# Reorganize the use cases when implmenting the SN side of diff
		if numPvs and not numIDs:
			liveFlds = [self._getLiveFldDict(Pv, objType) for Pv, objType in 
			            zip(Pvs, self._objTypes)]
			if checkPmgr or numPvs == 1:
				pmgrFlds = [self._getPmgrFldDict(Pv, objType, hutch) for Pv,
				            objType, hutch in zip(
					            Pvs, self._objTypes, flatten(self._hutches))]
				maxColLen = len(max(flatten(
					[liveFld.values() for liveFld in liveFlds] + 
					[pmgrFld.values() for pmgrFld in pmgrFlds]), key=len)) + 1
				if maxColLen > minColLen:
					minColLen = maxColLen
				diffDfs = [self._getDiffDf(
					[Pv], [liveFld, pmgrFld], fldMap, minColLen, offSet) for 
					Pv, liveFld, pmgrFld in zip(Pvs, liveFlds, pmgrFlds)]
			else:
				maxColLen = len(max(flatten(
					[liveFld.values() for liveFld in liveFlds]), key=len)) + 1
				if maxColLen > minColLen:
					minColLen = maxColLen
				diffDfs = [self._getDiffDf(Pvs, liveFlds, fldMap, minColLen, 
				                           offSet)]
		else:
			# Future additions:
			# Once the search function is working, add a way to print diffs
			# between:
			# - Live devices and pmgr entries
			# - Different pmgr entries
			# - Pmgr entry and the rec_base it is connected to if it exists
			raise NotImplementedError()

		paramLen, toolTipLen = [], []
		for diffDf in diffDfs:
			if diffDf.shape[0] != 0:
				paramLen.append(diffDf['alias'].str.len().max() + offSet)
				toolTipLen.append(diffDf['tooltip'].str.len().max())

		for i, diffDf in enumerate(diffDfs):
			if not tooltip:
				diffDf = diffDf.drop('tooltip', 1)
				index  = ['Param']
				lenDiffCols = [max(paramLen)]
			else:
				index  = ['Param', 'Tooltip']
				lenDiffCols = [max(paramLen), max(toolTipLen)]
			motorDesc = liveFlds[i]["FLD_DESC"]
			print "{0} PV: {1}".format(devName.capitalize(), Pvs[i])
			print "{0} Description: {1}".format(devName.capitalize(), motorDesc)
			print "Number of Diffs: {0}".format(diffDf.shape[0])
			if diffDf.shape[0] != 0:
				print self._view(diffDf, index, offSet = offSet, 
				                 minColLen = minColLen, lenCols = lenDiffCols)				

	def _inferFromArgs(self, args):
		"""
		Processes a key word argument and performs any preprocessing necessary.
		"""
		Pvs, IDs = [], []
		for arg in args:
			if isnumber(arg):
				if len(arg) == 2:
					# This is a bit of an assumption that IDs (SNs) will never 
					# only be len 2.
					Pvs.append(arg)
				else:
					IDs.append(str(arg))
			else:
				Pvs.append(arg)
		Pvs = parsePvArguments(Pvs)
		return Pvs, IDs

	def _inferFromPvs(self, Pvs):
		if not self._hutches:
			for Pv in Pvs:
				hutches, _ = self._getValidHutches(Pv[:3])
				if hutches:
					self._hutches.append(hutches)
				else:
					break
			# Porbably need to turn this into its own method
			if len(self._hutches) != len(Pvs):
				self._hutches = []
				print "Could not infer hutch(es) from PV(s). Please enter hutch:"
				for Pv in Pvs:
					inpHutch = None
					while not inpHutch:
						inpHutch = input("{0} - ".format(Pv))
						if inpHutch not in self._allHutches:
							print "Invalid hutch entry: '{0}'".format(inpHutch)
							inpHutch = None
					self._hutches.append([inpHutch])

		if not self._objTypes:
			for Pv, hutch in zip(Pvs, self._hutches):
				# Yes I am a lazy sob
				if len(self._allObjTypes) == 1:
					self._objTypes.append(list(self._allObjTypes)[0])
				else:
					# Fill this in at some point
					raise NotImplementedError()

	def _getDiffDf(self, Pvs, fldDicts, fldMap, minValColLen = 10, offSet = 0):
		"""
		Returns a df with the alias, tooltip and values of the different fields.
		"""
		idxDiffs  = self._getDiffFlds(fldDicts)
		diffDicts = [{i:fldDict[i] for i in idxDiffs} for fldDict in fldDicts]
		diffDf    = fldMap.loc[idxDiffs][['alias', 'tooltip']].reset_index()
		nPvs, nDiffDicts = len(Pvs), len(diffDicts)
		if nPvs != nDiffDicts:
			for Pv in Pvs:
				Pvs.append("Pmgr")
				if len(Pvs) == nDiffDicts:
					break
		Pvs = [Pv.rjust(minValColLen - 1 + offSet, "-") for Pv in Pvs]
		for Pv, diffDict in zip(Pvs, diffDicts):
			diffDf[Pv] = diffDf['index'].map(diffDict)
		diffDf = diffDf.drop('index', 1)
		return diffDf

	def _getDiffFlds(self, fldDicts):
		"""Returns the names of the fields that are different."""
		diffFlds = []
		for fld in fldDicts[0].keys():
			val = fldDicts[0][fld]
			for fldDict in islice(fldDicts, 1, len(fldDicts)):
				if fldDict[fld] != val and fld not in diffFlds:
					diffFlds.append(fld)
		diffFlds.sort()
		return diffFlds
		
	def _getPmgrFldDict(self, Pv, objType, hutch):
		"""
		Returns a dictionary of values for the pmgr entry of the inputted device 
		Pv.
		"""
		self._pmgr = self._getPmgr(objType, hutch)
		self._pmgr.updateTables()
		fldMap = self._objTypeFldMaps[objType]
		fldID  = self._getValWhereTrue(self._objTypeIDs, 'objTypeIDs', 
		                               'objType', objType)
		PvExt  = fldMap.pv[fldID]
		try:
			devID  = str(get(Pv + PvExt))
		except pyexc:
			print "Could not connect to '{0}'.".format(Pv + PvExt)
			return None
		try:
			objID  = self._getPmgrObjFromDevID(devID, fldID)
		except pmgrKeyError:
			print "Key {0} for {1} not found in the pmgr.".format(devID, Pv)
			return None
		return self._getObjFldDict(objID, objType)

	def _getPmgrObjFromDevID(self, devID, fldID):
		"""Returns the id of the object whose fldID matches the devID."""
		for objID in self._pmgr.objs.keys():
		    if devID == self._pmgr.objs[objID][fldID]:
			    return objID
		raise pmgrKeyError(devID)

	def _getObjFldDict(self, objID, objType):
		"""Returns the field dictionary of the object given the object ID."""
		pmgrObj = self._pmgr.objs[objID]
		# Find out what exception gets raised if there is an invalid config
		# -----------------------------------------------------------------
		pmgrCfg = self._pmgr.cfgs[pmgrObj['config']]
		# -----------------------------------------------------------------
		fldDict = {}
		fldMap  = self._objTypeFldMaps[objType]
		for fld in fldMap.index:
			try:
				fldDict[fld] = str(pmgrCfg[fld])
			except KeyError:
				fldDict[fld] = str(pmgrObj[fld])
		return fldDict
		
	#############################################################################
	#                                   Import                                  #
	#############################################################################

	def Import(self):
		raise NotImplementedError()

	#############################################################################
	#                                    New                                    #
	#############################################################################

	def New(self):
		raise NotImplementedError()

	#############################################################################
	#                                    Edit                                   #
	#############################################################################
	
	def Edit(self):
		raise NotImplementedError()

	#############################################################################
	#                                    Save                                   #
	#############################################################################

	def Save(self):
		raise NotImplementedError()

	#############################################################################
	#                                   Apply                                   #
	#############################################################################

	def Apply(self):
		raise NotImplementedError()

	#############################################################################
	#                                   Revert                                  #
	#############################################################################

	def Revert(self):
		raise NotImplementedError()

	#############################################################################
	#                                   Refresh                                 #
	#############################################################################

	def Refresh(self, mode = None):
		"""Reinitializes the metadata using the pmgr or the csv."""
		self._setMode(local)
		self._setAttrs()

	#############################################################################
	#                                    Pmgr                                   #
	#############################################################################

	def Pmgr(self):
		raise NotImplementedError()

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
	def mode(self):
		"""Returns the mode devconfig is currently running in."""
		return self._mode
	@mode.setter
	def mode(self, mode):
		"""Sets local mode to inputted mode (pmgr/local)."""
		self._setMode(mode)

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
		
	@property
	def hutchAliases(self, hutches=set()):
		# Will need to modify the set and return dict methods for hutch aliases
		# as the values are going to be sets.
		raise NotImplementedError()
	@hutchAliases.setter
	def hutchAliases(self, hutchAliasesDict):
		# Need to make sure that when setting aliases that all hutches are valid
		raise NotImplementedError()

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

#################################################################################
#                               Helper Functions                                #
#################################################################################

def isiterable(obj):
	"""
	Function that determines if an object is an iterable, but not including 
	strings.
	"""
	if isinstance(obj, basestring):
		return False
	else:
		return isinstance(obj, Iterable)

def isnumber(obj):
	"""Checks if the input is a number."""
	if isinstance(obj, basestring):
		try:
			float(obj)
			return True
		except ValueError:
			return False
	elif isinstance(obj, float) or isinstance(obj, int):
		return True
	else:
		return False

def flatIter(inpIter):
	"""Recursively iterate through values in nested iterables."""
	for val in inpIter:
		if isiterable(val):
			for inVal in flatIter(val):
				yield inVal
		else:
			yield val

def flatten(inpIter):
	"""Returns a flattened list of the inputted iterator."""
	return list(flatIter(inpIter))

def isempty(seq):
	"""Checks if an iterable (nested or not) is empty."""
	return not any(1 for _ in flatIter(seq))

def parsePvArguments(PvArguments):
	"""
	Parses PV input arguments and returns a set of motor PVs that will have
	the pmgrUtil functions applied to.
	"""
	if len(PvArguments) == 0: return None
	fullPvs = []
	basePv = ''
	for arg in PvArguments:
		if getBasePv(arg):
			basePv = getBasePv(arg)
		if '-' in arg:
			splitArgs = arg.split('-')
			if getBasePv(splitArgs[0]) == basePv: 
				fullPvs.append(splitArgs[0])
			start = int(splitArgs[0][-2:])
			end = int(splitArgs[1])
			for i in range(start+1, end+1):
				fullPvs.append(basePv + "{:02}".format(i))
		elif basePv == getBasePv(arg):
			fullPvs.append(arg)
		elif len(arg) < 3:
			fullPvs.append(basePv + "{:02}".format(int(arg)))
		else:
			print "invalid arg: {0}.".format(arg)
	return fullPvs

def getBasePv(Pv):
	"""
	Returns the first base PV found in the list of PVArguments. It looks for the 
	first colon starting from the right and then returns the string up until
	the colon. Takes as input a string or a list of strings.
	"""
	if ':' not in Pv or len(Pv) < 9: 
		return None
	for i, char in enumerate(Pv[::-1]):
		if char == ':':
			return Pv[:-i]

		
#################################################################################
#                             Stand Alone Routines                              #
#################################################################################

def Diff(*args, **kwargs):
	"""Returns the diffs using the inputted paramaters."""
	dCfg = devconfig()
	dCfg.Diff(*args, **kwargs)

#################################################################################
#                                     Main                                      #
#################################################################################

if __name__ == "__main__":
	validCommands = {"diff":Diff}
	validOptions  = ["hutches", "objTypes", "mode"]
	parser = OptionParser()
	parser.add_option('--hutch', action='store', type='string', dest='hutches', 
	                  default=None)
	parser.add_option('--objType', action='store', type='string', dest='objTypes', 
	                  default=None)
	parser.add_option('--mode', action='store', type='string', dest='mode', 
	                  default=None)
	parser.add_option('--pmgr', '-p', action='store_true', dest='pmgr', 
	                  default=False)
	parser.add_option('--tooltip', '-t', action='store_true', dest='tooltip', 
	                  default=False)
	parser.add_option('--summary', '-s', action='store_true', dest='summary', 
	                  default=False)

	options, args = parser.parse_args()
	kwargs = vars(options)
	for cmd in validCommands.keys():
		if cmd in args:
			args.remove(cmd)
			validCommands[cmd](*args, **kwargs)

