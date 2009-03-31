# -*- coding: utf-8 -*-

# HDTV - A ROOT-based spectrum analysis software
#  Copyright (C) 2006-2009  The HDTV development team (see file AUTHORS)
#
# This file is part of HDTV.
#
# HDTV is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# HDTV is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with HDTV; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

import ROOT
import os
import glob

import hdtv.cmdline
import hdtv.cmdhelper
import hdtv.color
import hdtv.cal
 
from hdtv.spectrum import Spectrum, FileSpectrum
from hdtv.specreader import SpecReaderError


# Don't add created spectra to the ROOT directory
ROOT.TH1.AddDirectory(ROOT.kFALSE)

class SpecInterface:
	"""
	User interface to work with 1-d spectra
	"""
	def __init__(self, window, spectra):
		print "Loaded user interface for working with 1-d spectra"
	
		self.window = window
		self.spectra= spectra
		self.caldict = dict()
		
		# tv commands
		self.tv = TvSpecInterface(self)
		
		# good to have as well...
		self.window.AddHotkey(ROOT.kKey_PageUp, self._HotkeyShowPrev)
		self.window.AddHotkey(ROOT.kKey_PageDown, self._HotkeyShowNext)
		
		# register common tv hotkeys
		self.window.AddHotkey([ROOT.kKey_N, ROOT.kKey_p], self._HotkeyShowPrev)
		self.window.AddHotkey([ROOT.kKey_N, ROOT.kKey_n], self._HotkeyShowNext)
		self.window.AddHotkey(ROOT.kKey_Equal, self.spectra.RefreshAll)
		self.window.AddHotkey(ROOT.kKey_t, self.spectra.RefreshVisible)
		self.window.AddHotkey(ROOT.kKey_n,
		        lambda: self.window.EnterEditMode(prompt="Show spectrum: ",
		                                   handler=self._HotkeyShow))
		self.window.AddHotkey(ROOT.kKey_a,
		        lambda: self.window.EnterEditMode(prompt="Activate spectrum: ",
		                                   handler=self._HotkeyActivate))
	
	def _HotkeyShow(self, arg):
		""" 
		ShowObjects wrapper for use with Hotkey
		"""
		try:
			ids = hdtv.cmdhelper.ParseRange(arg.split())
			if ids == "NONE":
				self.spectra.HideAll()
			elif ids == "ALL":
				self.spectra.ShowAll()
			else:
				self.spectra.ShowObjects(ids)
		except ValueError:
			self.window.viewport.SetStatusText("Invalid spectrum identifier: %s" % arg)


		
	def _HotkeyActivate(self, arg):
		"""
		ActivateObject wrapper for use with Hotkey
		"""
		try:
			ID = int(arg)
			self.spectra.ActivateObject(ID)
		except ValueError:
			self.window.viewport.SetStatusText("Invalid id: %s" % arg)
		except KeyError:
			self.window.viewport.SetStatusText("No such id: %d" % ID)

	def _HotkeyShowNext(self):
		"""
		Show next spectrum and activate it automatically
		"""
		self.spectra.ShowNext()
		ID = list(self.spectra.visible)[0]
		self.spectra.ActivateObject(ID)

	def _HotkeyShowPrev(self):
		"""
		Show previous spectrum and activate it automatically
		"""
		self.spectra.ShowPrev()
		ID = list(self.spectra.visible)[0]
		self.spectra.ActivateObject(ID)


	def LoadSpectra(self, files):
		"""
		Load spectra from files
		
		It is possible to use wildcards. 
		"""
		# Avoid multiple updates
		self.window.viewport.LockUpdate()
		# only one filename is given
		if type(files) == str or type(files) == unicode:
			files = [files]
		loaded = [] 
		for f in files:
			# put fmt if available
			f = f.rsplit("'", 1)
			if len(f) == 1 or not f[1]:
				(fname, fmt) = (f[0], None)
			else:
				(fname, fmt) = f
			path = os.path.expanduser(fname)
			for fname in glob.glob(path):
				try:
					spec = FileSpectrum(fname, fmt)
				except (OSError, SpecReaderError):
					print "Warning: could not load %s'%s" %(fname, fmt)
				else:
					ID = self.spectra.Add(spec)
					spec.SetColor(hdtv.color.ColorForID(ID))
					loaded.append(ID)
		if len(loaded)>0:
			self.spectra.ActivateObject(loaded[-1])
		# Update viewport if required
		self.window.Expand()
		self.window.viewport.UnlockUpdate()
		return loaded


	def FindSpectrumByName(self, name):
		"""
		Find the spectrum object whose ROOT histogram has the given name.
		If there are several such objects, one of them (in undefined ordering)
		is returned. If there is none, None is returned.
		"""
		for obj in self.spectra.objects.itervalues():
			if isinstance(obj, hdtv.spectrum.Spectrum):
				if obj.fHist != None and obj.fHist.GetName() == name:
					return obj
		return None
			

	def GetCalsFromList(self, fname):
		"""
		Reads calibrations from a calibration list file. The file has the format
		<specname>: <cal0> <cal1> ...
		The calibrations are written into the calibration dictionary.
		"""
		try:
			f = open(fname, "r")
		except IOError, msg:
			print "Error opening file: %s" % msg
			return False
		linenum = 0
		for l in f:
			linenum += 1
			# Remove comments and whitespace; ignore empty lines
			l = l.split('#', 1)[0].strip()
			if l == "":
				continue
			try:
				(k, v) = l.split(':', 1)
				name = k.strip()
				coeff = [ float(s) for s in v.split() ]
				self.caldict[name] = coeff
			except ValueError:
				print "Warning: could not parse line %d of file %s: ignored." % (linenum, fname)
			else:
				# FIXME: Maybe Norbert had different plans here?
				spec = self.FindSpectrumByName(name)
				if spec:
					spec.SetCal(self.caldict[name])
 		f.close()
		return True


class TvSpecInterface:
	"""
	TV style commands for the spectrum interface.
	"""
	def __init__(self, specInterface):
		self.specIf = specInterface
		self.spectra = self.specIf.spectra
		
		# register tv commands
		hdtv.cmdline.command_tree.SetDefaultLevel(1)
		
		
		# spectrum commands
		hdtv.cmdline.AddCommand("spectrum get", self.SpectrumGet, level=0, minargs=1,
		                        fileargs=True)
		parser = hdtv.cmdline.HDTVOptionParser(prog="spectrum list", usage="%prog [OPTIONS]")
		parser.add_option("-v", "--visible", action="store_true",
                          default=False, help="list only visible (and active) spectra")
		hdtv.cmdline.AddCommand("spectrum list", self.SpectrumList, nargs=0, parser=parser)
		hdtv.cmdline.AddCommand("spectrum delete", self.SpectrumDelete, minargs=1,
		                        usage="spectrum delete <ids>")
		hdtv.cmdline.AddCommand("spectrum activate", self.SpectrumActivate, nargs=1,
		                        usage="spectrum activate <id>")
		hdtv.cmdline.AddCommand("spectrum show", self.SpectrumShow, minargs=1,
		                        usage="spectrum show <ids>|all|none")
		hdtv.cmdline.AddCommand("spectrum update", self.SpectrumUpdate, minargs=1,
		                        usage="spectrum update <ids>|all|shown")
		hdtv.cmdline.AddCommand("spectrum write", self.SpectrumWrite, minargs=1, maxargs=2,
		                        usage="spectrum write <filename>'<format> [id]")
		hdtv.cmdline.AddCommand("spectrum normalization", self.SpectrumNormalization,
		                        minargs=1,
		                        usage="spectrum normalization [ids] <norm>")

		# calibration commands
		hdtv.cmdline.AddCommand("calibration position read", self.CalPosRead, minargs=1,
		                        fileargs=True,
		                        usage="calibration position read <filename> [ids]")
		hdtv.cmdline.AddCommand("calibration position enter", self.CalPosEnter, minargs=4,
		                        usage="calibration position enter <ch0> <E0> <ch1> <E1> [ids]")
		hdtv.cmdline.AddCommand("calibration position set", self.CalPosSet, minargs=2,
		                        usage="calibration position set <deg> <p0> <p1> <p2> ... [ids]")
		hdtv.cmdline.AddCommand("calibration position getlist", self.CalPosGetlist, nargs=1,
		                        fileargs=True,
		                        usage="calibration position getlist <filename>")

	
	def SpectrumList(self, args, options):
		"""
		Print a list of all spectra 
		"""
		# FIXME: args and options? Why?
		self.spectra.ListObjects()
	

	def SpectrumGet(self, args):
		"""
		Load Spectrum from files
		"""
		loaded = self.specIf.LoadSpectra(files = args)
		if len(loaded) == 0:
			print "Warning: no spectra loaded."
		elif len(loaded) == 1:
			print "Loaded 1 spectrum"
		else:
			print "Loaded %d spectra" % len(loaded)
		

	def SpectrumDelete(self, args):
		""" 
		Deletes spectra 
		"""
		try:
			ids = hdtv.cmdhelper.ParseRange(args)
			if ids == "NONE":
				return
			elif ids == "ALL":
				ids = self.spectra.keys()
			self.spectra.RemoveObjects(ids)
		except:
			return "USAGE"
					

	def SpectrumActivate(self, args):
		"""
		Activate one spectra
		"""
		try:
			ID = int(args[0])
			self.spectra.ActivateObject(ID)
		except ValueError:
			return "USAGE"
		
		
	def SpectrumShow(self, args):
		"""
		Shows spectra
		"""
		try:
			keywords = ["none", "all", "next", "prev", "first", "last"]
			ids = hdtv.cmdhelper.ParseRange(args, keywords)
			if ids == "NONE":
				self.spectra.HideAll()
			elif ids == "ALL":
				self.spectra.ShowAll()
			elif ids == "NEXT":
				self.spectra.ShowNext()
			elif ids == "PREV":
				self.spectra.ShowPrev()
			elif ids == "FIRST":
				self.spectra.ShowFirst()
			elif ids == "LAST":
				self.spectra.ShowLast()
			else:
				self.spectra.ShowObjects(ids)
			ID = list(self.spectra.visible)[0]
			self.spectra.ActivateObject(ID)
		except:
			return "USAGE"

			
	def SpectrumUpdate(self, args):
		"""
		Refresh spectra
		"""
		try:
			ids = hdtv.cmdhelper.ParseRange(args, ["all", "shown"])
			if ids == "ALL":
				self.spectra.RefreshAll()
			elif ids == "SHOWN":
				self.spectra.RefreshVisible()
			else:
				self.spectra.Refresh(ids)
		except:
			return "USAGE"

			
	def SpectrumWrite(self, args):
		"""
		Write Spectrum to File
		"""
		try:
			(fname, fmt) = args[0].rsplit("'", 1)
			if len(args) == 1:
				ID = self.spectra.activeID
			elif len(args)==2:
				ID = int(args[1])
			else:
				print "There is just one index possible here."
				raise ValueError
			try:
				self.spectra[ID].WriteSpectrum(fname, fmt)
				print "wrote spectrum with id %d to file %s" %(ID, fname)
			except KeyError:
				 print "Warning: there is no spectrum with id: %s" %ID
		except ValueError:
			return "USAGE"
			
	
	def SpectrumNormalization(self, args):
		"Set normalization for spectrum"
		try:
			if len(args) == 1:
				ids = [ self.spectra.activeID ]
			else:
				ids = hdtv.cmdhelper.ParseRange(args[:-1])
				if ids == "NONE":
					ids = []
				elif ids == "ALL":
					ids = self.spectra.keys()
			
			norm = float(args[-1])
		except ValueError:
			return "USAGE"
			
		for ID in ids:
			try:
				self.spectra[ID].SetNorm(norm)
			except KetError:
				print "Warning: there is no spectrum with id: %s" % ID
						
			
	def CalPosRead(self, args):
		"""
		Read calibration from file
		"""
		try:
			fname = args[0]
			cal = hdtv.cal.CalFromFile(fname)
			if len(args[1:])==0:
				if self.spectra.activeID==None:
					print "No index is given and there is no active spectrum"
					raise ValueError
				else:
					ids = [self.spectra.activeID]
			else:
				ids = hdtv.cmdhelper.ParseRange(args[1:])
		except ValueError:
			return "USAGE"
		else:	
			if ids=="NONE":
				return
			elif ids=="ALL":
				ids = self.spectra.keys()
		
			for ID in ids:
				try:
					self.spectra[ID].SetCal(cal)
					print "calibrated spectrum with id %d" %ID
				except KeyError:
					print "Warning: there is no spectrum with id: %s" %ID
			self.specIf.window.Expand()
			return True
			
		
	def CalPosEnter(self, args):
		"""
		Create calibration from two pairs of channel and energy
		"""
		try:
			pairs = []
			pairs.append([float(args[0]), float(args[1])])
			pairs.append([float(args[2]), float(args[3])])
			cal = hdtv.cal.CalFromPairs(pairs)
			if len(args[4:])==0:
				if self.spectra.activeID==None:
					print "No index is given and there is no active spectrum"
					raise ValueError
				else:
					ids = [self.spectra.activeID]
			else:
				ids = hdtv.cmdhelper.ParseRange(args[4:])
		except (ValueError, IndexError):
			return "USAGE"
		else:
			if ids=="NONE":
				return
			elif ids=="ALL":
				ids = self.spectra.keys()
			for ID in ids:
				try:
					self.spectra[ID].SetCal(cal)
					print "calibrated spectrum with id %d" %ID
				except KeyError:
					print "Warning: there is no spectrum with id: %s" %ID
			self.specIf.window.Expand()
			return True

		
	def CalPosSet(self, args):
		"""
		Create calibration from the coefficients p of a polynom
		n is the degree of the polynom
		"""
		try:
			deg = int(args[0])
			calpoly = [float(i) for i in args[1:deg+2]]
			if len(args[deg+2:])==0:
				if self.spectra.activeID==None:
					print "No index is given and there is no active spectrum"
					raise ValueError
				else:
					ids = [self.spectra.activeID]
			else:
				ids = hdtv.cmdhelper.ParseRange(args[deg+2:])
		except (ValueError, IndexError):
			return "USAGE"
		else:
			if ids=="NONE":
				return
			elif ids=="ALL":
				ids = self.spectra.keys()
			for ID in ids:
				try:
					self.spectra[ID].SetCal(calpoly)
					print "calibrated spectrum with id %d" %ID
				except KeyError:
					print "Warning: there is no spectrum with id: %s" %ID
			self.specIf.window.Expand()
			return True
	
		
	def CalPosGetlist(self, args):
		"""
		Read calibrations for several spectra from file
		"""
		self.specIf.GetCalsFromList(args[0])


# plugin initialisation
import __main__
if not hasattr(__main__,"window"):
	import hdtv.window
	__main__.window = hdtv.window.Window()
if not hasattr(__main__, "spectra"):
	import hdtv.drawable
	__main__.spectra = hdtv.drawable.DrawableCompound(__main__.window.viewport)
__main__.s = SpecInterface(__main__.window, __main__.spectra)
