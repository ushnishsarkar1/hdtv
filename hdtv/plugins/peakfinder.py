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

#-------------------------------------------------------------------------------
# Peak finding and fitting plugin for HDTV
#-------------------------------------------------------------------------------


import hdtv.cmdline
import hdtv.fitter
import hdtv.peakmodels
import hdtv.options
import hdtv.spectrum
import hdtv.color
import ROOT

class PeakFinder:
    
    def __init__(self, spectra, defaultFitter):
        
        self.spectra = spectra
        self.defaultFitter = defaultFitter
        hdtv.ui.msg("loaded PeakFinder plugin")
        
        # Register configuration variables for fit peakfind
        opt = hdtv.options.Option(default = 2.5)
        hdtv.options.RegisterOption("fit.peakfind.sigma", opt)    
        opt = hdtv.options.Option(default = 0.05)
        hdtv.options.RegisterOption("fit.peakfind.threshold", opt)
        opt = hdtv.options.Option(default = False, parse = hdtv.options.ParseBool)
        hdtv.options.RegisterOption("fit.peakfind.auto_fit", opt)

        prog = "fit peakfind"
        description = "Search for peaks in active spectrum in given range"
        usage = "%prog <start> <end>"
        parser = hdtv.cmdline.HDTVOptionParser(prog = prog, description = description, usage = usage)
        parser.add_option("-S", "--sigma", action = "store", default = hdtv.options.Get("fit.peakfind.sigma"),
                        help = "FWHM of peaks")
        parser.add_option("-T", "--threshold", action = "store", default = hdtv.options.Get("fit.peakfind.threshold"),
                        help = "Threshold of peaks to accept in fraction of the amplitude of highest peak (in %)")
        parser.add_option("-a", "--auto-fit", action = "store_true", default = hdtv.options.Get("fit.peakfind.auto_fit"),
                        help = "automatically fit found peaks")
#        parser.add_option("-r", "--reject", action = "store_true", default = False,
#                        help = "reject fits with unreasonable values")
        hdtv.cmdline.AddCommand(prog, self.PeakSearch, level = 4, parser = parser, minargs = 0, fileargs = False)
        
 
## FIXME or remove:
#        prog = "fit bgfit"
#        description = "XXX"
#        usage = "%prog <start> <end>"
#        parser = hdtv.cmdline.HDTVOptionParser(prog = prog, description = description, usage = usage)
#        hdtv.cmdline.AddCommand(prog, self.BGFit, level = 4, parser = parser, minargs = 0, fileargs = False)
#        

#    def BGFit(self, args, options):
#        """
#        Do a background fit
#        """
#        # Background fit
#        sid = self.spectra.activeID
#        tSpec = ROOT.TSpectrum()
#        
#        spec = self.spectra[self.spectra.activeID]

#        hist = spec.fHist.__class__(spec.fHist) # Copy hist here 
#        # TODO: draw background
#        hbg = hist.ShowBackground(20, "goff")
#        print "hbg", hbg
#        bgspec = hdtv.spectrum.Spectrum(hbg, cal=spec.cal)
#        
#        bspec = hdtv.spectrum.SpectrumCompound(spec.viewport, bgspec)
#        sid = self.spectra.Add(bgspec)
#        bgspec.SetColor(hdtv.color.ColorForID(sid))
#        print "BGSPec", sid

    
    def PeakSearch(self, args, options):
        """
        Search for peaks using ROOTS peak search function
        """
        try:
            if not self.spectra.activeID in self.spectra.visible:
                hdtv.ui.warn("Active spectrum is not visible, no action taken")
                return True
        except KeyError:
            hdtv.ui.error("No active spectrum")
            return False
        

        sid = self.spectra.activeID
        tSpec = ROOT.TSpectrum()

        spec = self.spectra[sid]
        # Copy hist here so we can safely modify ranges, etc. below
        # as copy.copy is not working we have to call the C++ copy constructor
        hist = spec.fHist.__class__(spec.fHist)

        try:
            sigma_Ch = spec.cal.E2Ch(float(options.sigma)) - spec.cal.E2Ch(float(0.0))
            assert sigma_Ch > 0, "Sigma must be > 0"
            print "sigma_ch", sigma_Ch
            sigma_E = float(options.sigma) 
            threshold = float(options.threshold)
        except ValueError:
            hdtv.ui.error("Invalid sigma/threshold")
            return False
        
        autofit = options.auto_fit

        # Init start and end region
        start_E = 0.0
        start_Ch = spec.cal.E2Ch(start_E)
        end_Ch = hist.GetNbinsX()
        end_E = spec.cal.Ch2E(end_Ch)
        
        try:
            if len(args) > 0:
                start_E = float(args[0])
                start_Ch = spec.cal.E2Ch(start_E)
                
            if len(args) == 2:
                end_E = float(args[1])
                end_Ch = spec.cal.E2Ch(end_E)
        except ValueError:
            hdtv.ui.error("Invalid start/end arguments")
            return False

        text = "Search Peaks in region "
        text += str(start_E) + "--" + str(end_E)
        text += " (sigma=" + str(sigma_E) 
        text += " threshold=" + str(threshold*100) + " %)"
        hdtv.ui.msg(text)
        
        # Invoke ROOT's peak finder
        hist.SetAxisRange(start_Ch, end_Ch)
        num_peaks = tSpec.Search(hist, sigma_Ch, "goff", threshold)
        foundpeaks = tSpec.GetPositionX()

        parameter = dict()
        
        # Sort by position
        tmp = list()
        for i in range(0, num_peaks):
            tmp.append(foundpeaks[i]) # convert from array to list
        tmp.sort()
        foundpeaks = tmp
        
        # Store peaks
        
        # TODO:
        # * Reject negative FWHM, Volume
        # * Reject unreasonable FWHM
        while len(foundpeaks)>0:
             p = foundpeaks.pop(0)
             fitter = self.defaultFitter.Copy()
             fit = hdtv.fit.Fit(fitter, cal = spec.cal)
             pos_E = spec.cal.Ch2E(p)
             pos_Ch = p
             bin = hist.GetXaxis().FindBin(pos_Ch)
             yp = hist.GetBinContent(bin)
             fit.PutPeakMarker(pos_E)
             # collect multipletts
             if autofit:
                 region_width = sigma_E * 5. # TODO: something sensible here
                 # left region marker
                 fit.PutRegionMarker(pos_E - region_width / 2.)
                 limit = pos_E + region_width
                 while len(foundpeaks)>0 and spec.cal.Ch2E(foundpeaks[0]) <= limit:
                    next = foundpeaks.pop(0)
                    pos_E = spec.cal.Ch2E(next)
                    limit = pos_E + region_width
                    fit.PutPeakMarker(pos_E)
                 # right region marker
                 fit.PutRegionMarker(pos_E + region_width / 2.)
                 fit.FitPeakFunc(spec, silent = True)
             
             ID = spec.AddFit(fit)
             fit.title = fit.title + "(*)"

## FIXME or remove: unfortunately this code is specific for each peakmodel!
##                reject = False
##                if options.reject:
##                    if len(fit.peaks) == 1: # TODO: Do something sensible for doublets (when we are fitting them here)
##                        if fit.peaks[0].width <= 0.0 or fit.peaks[0].vol <= 0.0 or fit.peaks[0].width > 7 * sigma_E:
##                            text  = "Rejecting peak @" + str(fit.peaks[0].pos_cal)
##                            text += " keV (width = " + str(fit.peaks[0].width) 
##                            text += " vol = " + str(fit.peaks[0].vol) + ")"
##                            hdtv.ui.msg(text)
##                            reject = True
##                            num_peaks -= 1
##                if not reject:
##                    ID = spec.AddFit(fit)
##                    fit.title = fit.title + "(*)"
        
        hdtv.ui.msg("Found " + str(num_peaks) + " peaks")
        return True
    
# plugin initialisation
import __main__
if not hasattr(__main__, "spectra"):
    import hdtv.drawable
    __main__.spectra = hdtv.drawable.DrawableCompound(__main__.window.viewport)
if hasattr(__main__,"f"):
    defaultFitter=__main__.f.defaultFitter
else:
    import hdtv.fitter
    defaultFitter = hdtv.fitter.Fitter("theuerkauf", 2)
__main__.peakfinder = PeakFinder(__main__.spectra, __main__.f.defaultFitter)
