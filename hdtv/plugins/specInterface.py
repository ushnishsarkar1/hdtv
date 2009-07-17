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


    def LoadSpectra(self, patterns, ID=None):
        """
        Load spectra from files matching patterns.
        
        If ID is specified, the spectrum is stored with id ID, possibly
        replacing a spectrum that was there before.
        """
        # Avoid multiple updates
        self.window.viewport.LockUpdate()
        # only one filename is given
        if type(patterns) == str or type(patterns) == unicode:
            patterns = [patterns]

        if ID != None and len(patterns) > 1:
            print "Error: if you specify an ID, you can only give one pattern"
            self.window.viewport.UnlockUpdate()
            return
        
        loaded = [] 
        for p in patterns:
            # put fmt if available
            p = p.rsplit("'", 1)
            if len(p) == 1 or not p[1]:
                (fpat, fmt) = (p[0], None)
            else:
                (fpat, fmt) = p

            files = glob.glob(os.path.expanduser(fpat))
            
            if len(files) == 0:
                print "Warning: %s: no such file" % fpat
            elif ID != None and len(files) > 1:
                print "Error: pattern %s is ambiguous and you specified an ID" % fpat
                break
                
            files.sort()
            
            for fname in files:
                try:
                    spec = FileSpectrum(fname, fmt)
                except (OSError, SpecReaderError):
                    print "Warning: could not load %s'%s" % (fname, fmt)
                else:
                    if ID == None:
                        sid = self.spectra.Add(spec)
                    else:
                        sid = self.spectra.Insert(spec, ID)

                    spec.SetColor(hdtv.color.ColorForID(sid))
                    loaded.append(sid)
                    
                    if fmt == None:
                        print "Loaded %s into %d" % (fname, sid)
                    else:
                        print "Loaded %s'%s into %d" % (fname, fmt, sid)
        
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
        fname = os.path.expanduser(fname)
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
    
    def ApplyCalibration(self, cal, ids):
        """
        Apply calibration cal to spectra with ids
        """
        for ID in ids:
            try:
                self.spectra[ID].SetCal(cal)
                print "calibrated spectrum with id %d" %ID
            except KeyError:
                print "Warning: there is no spectrum with id: %s" %ID
        self.window.Expand()

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
        parser = hdtv.cmdline.HDTVOptionParser(prog="spectrum get",
                     usage="%prog [OPTIONS] <pattern> [<pattern> ...]")
        parser.add_option("-i", "--id", action="store",
                          default=None, help="id for loaded spectrum")
        hdtv.cmdline.AddCommand("spectrum get", self.SpectrumGet, level=0, minargs=1,
                                fileargs=True, parser=parser)
        
        parser = hdtv.cmdline.HDTVOptionParser(prog="spectrum list", usage="%prog [OPTIONS]")
        parser.add_option("-v", "--visible", action="store_true",
                          default=False, help="list only visible (and active) spectra")
        hdtv.cmdline.AddCommand("spectrum list", self.SpectrumList, nargs=0, parser=parser)
        
        hdtv.cmdline.AddCommand("spectrum delete", self.SpectrumDelete, minargs=1,
                                usage="%prog <ids>")
        hdtv.cmdline.AddCommand("spectrum activate", self.SpectrumActivate, nargs=1,
                                usage="%prog <id>")
        hdtv.cmdline.AddCommand("spectrum show", self.SpectrumShow, minargs=1,
                                usage="%prog <ids>|all|none")
        hdtv.cmdline.AddCommand("spectrum update", self.SpectrumUpdate, minargs=1,
                                usage="%prog <ids>|all|shown")
        hdtv.cmdline.AddCommand("spectrum write", self.SpectrumWrite, minargs=1, maxargs=2,
                                usage="%prog <filename>'<format> [id]")
        hdtv.cmdline.AddCommand("spectrum normalization", self.SpectrumNormalization,
                                minargs=1,
                                usage="%prog [ids] <norm>")

        # calibration commands
        parser = hdtv.cmdline.HDTVOptionParser(prog="calibration position read",
                                               usage="%prog [OPTIONS] <filename>")
        parser.add_option("-s", "--spec", action="store",
                          default="all", help="spectrum ids to apply calibration to")
        hdtv.cmdline.AddCommand("calibration position read", self.CalPosRead, nargs=1,
                                fileargs=True, parser=parser)
        
        
        parser = hdtv.cmdline.HDTVOptionParser(prog="calibration position enter",
                     description=
"""Fit a calibration polynomial to the energy/channel pairs given.
Hint: specifying degree=0 will fix the linear term at 1. Specify spec=None
to only fit the calibration.""",
                     usage="%prog [OPTIONS] <ch0> <E0> [<ch1> <E1> ...]")
        parser.add_option("-s", "--spec", action="store",
                          default="all", help="spectrum ids to apply calibration to")
        parser.add_option("-d", "--degree", action="store",
                          default="1", help="degree of calibration polynomial fitted [default: %default]")
        parser.add_option("-f", "--show-fit", action="store_true",
                          default=False, help="show fit used to obtain calibration")
        parser.add_option("-r", "--show-residual", action="store_true",
                          default=False, help="show residual of calibration fit")
        parser.add_option("-t", "--show-table", action="store_true",
                          default=False, help="print table of energies given and energies obtained from fit")
        hdtv.cmdline.AddCommand("calibration position enter", self.CalPosEnter, minargs=2,
                                parser=parser)
        
        
        parser = hdtv.cmdline.HDTVOptionParser(prog="calibration position set",
                                               usage="%prog [OPTIONS] <p0> <p1> [<p2> ...]")
        parser.add_option("-s", "--spec", action="store",
                          default="all", help="spectrum ids to apply calibration to")
        hdtv.cmdline.AddCommand("calibration position set", self.CalPosSet, minargs=2,
                                parser=parser)
        
        
        hdtv.cmdline.AddCommand("calibration position getlist", self.CalPosGetlist, nargs=1,
                                fileargs=True,
                                usage="%prog <filename>")

    
    def SpectrumList(self, args, options):
        """
        Print a list of all spectra 
        """
        self.spectra.ListObjects(options.visible)
    

    def SpectrumGet(self, args, options):
        """
        Load Spectra from files
        """
        if options.id != None:
            ID = int(options.id)
        else:
            ID = None
        
        self.specIf.LoadSpectra(patterns = args, ID = ID)


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
                
    def ParseIDs(self, strings):
        # Parse IDs
        # Raises a ValueError if parsing fails
        ids = hdtv.cmdhelper.ParseRange(strings, ["ALL", "NONE", "ACTIVE"])
        if ids=="NONE":
            return []
        elif ids=="ACTIVE":
            if self.spectra.activeID==None:
                print "Error: no active spectrum"
                return False
            else:
                ids = [self.spectra.activeID]
        elif ids=="ALL":
            ids = self.spectra.keys()
        return ids
            
    def CalPosRead(self, args, options):
        """
        Read calibration from file
        """
        try:
            ids = self.ParseIDs(options.spec)
            if not ids:
                return
            
            # Load calibration
            fname = args[0]
            cal = hdtv.cal.CalFromFile(fname)
        except ValueError:
            return "USAGE"
        else:
            self.specIf.ApplyCalibration(cal, ids)        
            return True
            
        
    def CalPosEnter(self, args, options):
        """
        Create calibration from pairs of channel and energy
        """
        try:
            if len(args) % 2 != 0:
                print "Error: number of parameters must be even"
                return "USAGE"
            pairs = [[float(args[p]),float(args[p+1])] for p in range(0,len(args),2)]
            ids = self.ParseIDs(options.spec)
            if ids == False:
                return
            degree = int(options.degree)
        except ValueError:
            return "USAGE"
        try:
            cal = hdtv.cal.CalFromPairs(pairs, degree, options.show_table, 
                                        options.show_fit, options.show_residual)
        except (ValueError, RuntimeError), msg:
            print "Error: " + str(msg)
            return False
        else:
            self.specIf.ApplyCalibration(cal, ids)            
            return True


    def CalPosSet(self, args, options):
        """
        Create calibration from the coefficients p of a polynomial
        n is the degree of the polynomial
        """
        try:
            cal = [float(i) for i in args]
            ids = self.ParseIDs(options.spec)
            if not ids:
                return
            
        except ValueError:
            return "USAGE"
        else:
            self.specIf.ApplyCalibration(cal, ids)
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
