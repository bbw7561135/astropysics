#Copyright (c) 2008 Erik Tollerud (etolleru@uci.edu) 

"""
This module stores tools for oberving (pre- and post-) as well as functioning as
a "miscellaneous" bin for various corrections and calculations that don't have
a better place to live.

The focus is currently on optical astronomy, as that is what the primary author 
does.

Note that some of these functions require the dateutil package 
( http://pypi.python.org/pypi/python-dateutil , also included with matplotlib)
"""
#TODO: implement ability for Sites to translate ra/dec into alt/az given time/date
#TODO: add options for Observatory class to include more useful information
#TODO: exposure time calculator (maybe in phot instead?)
#TODO: make Extinction classes spec.HasSpecUnits and follow models framework?

from __future__ import division,with_statement
from .constants import pi
import numpy as np

from .utils import PipelineElement,DataObjectRegistry
#from .models import FunctionModel1DAuto as _FunctionModel1DAuto

def jd_to_gregorian(jd,bceaction=None,msecrounding=1e-5):
    """
    convert julian date number to a gregorian date and time
    
    output is dateutil UTC datetime objects or (datetime,bcemask) if bceaction
    is 'negreturn'
    
    bceaction indicates what to do if the result is a BCE year.   datetime 
    generally only supports positive years, so the following options apply:
    * 'raise' or None: raise an exception
    * 'neg': for any BCE years, convert to positive years (delta operations 
      in datetime will not be correct)
    * 'negreturn': same as 'neg', but changes the return type to a tuple with 
      the datetime objects as the first element and a boolean array that is True
      for the objects that are BCE as the second element.
    * a scalar: add this number to the year
    
    
    msecrounding does a fix for floating-point errors - if the seconds are 
    within the request number of seconds of an exact second, it will be set to
    that second 
    """
    import datetime
    
    jdn = np.array(jd,copy=False)
    scalar = jdn.shape == ()
    jdn = jdn.ravel()
    
    #implementation from http://www.astro.uu.nl/~strous/AA/en/reken/juliaansedag.html
    x2 = np.floor(jdn - 1721119.5)
    c2 = (4*x2 + 3)//146097
    x1 = x2 - (146097*c2)//4
    c1 = (100*x1 + 99)//36525
    x0 = x1 - (36525*c1)//100
    
    yr = 100*c2 + c1
    mon = (5*x0 + 461)//153
    day = x0 - (153*mon-457)//5 + 1
    
    mmask = mon>12
    mon[mmask] -= 12
    yr[mmask] += 1
    
    
    time = (jdn - np.floor(jdn) - 0.5) % 1
    if time == 0:
        hr = min = sec = msec = np.zeros_like(yr)
    elif time == 0.5:
        min = sec = msec = np.zeros_like(yr)
        hr = 12*np.ones_like(yr)
    else:
        hr = np.floor(time*24).astype(int)
        time = time*24 - hr
        min = np.floor(time*60).astype(int)
        time = time*60 - min
        sec = np.floor(time*60).astype(int)
        time = time*60 - sec
        msec = np.floor(time*1e6).astype(int)
        
        #rounding fix for floating point errors
        if msecrounding:
            msecundermask = (1-time) < msecrounding
            msecovermask = time < msecrounding
            msec[msecundermask|msecovermask] = 0
            sec[msecundermask] += 1
            min[sec==60] += 1
            sec[sec==60] = 0
            hr[min==60] += 1
            min[min==60] = 0
            hr[hr==24] = 0
            #date is always right
        
    
    try:
        from dateutil import tz
        tzi = tz.tzutc()
    except ImportError:
        tzi = None
    
    if bceaction is not None:
        if bceaction == 'raise':
            pass
        elif bceaction == 'neg' or bceaction == 'return':
            bcemask = yr<datetime.MINYEAR
            yr[bcemask] -= 1 #correct by 1 because JD=0 -> 1 BCE
            yr[bcemask]*= -1 
                
        else:
            yr += bceaction
    
    if scalar:
        res = datetime.datetime(yr[0],mon[0],day[0],hr[0],min[0],sec[0],msec[0],tzi)
    else:
        res = [datetime.datetime(*t,tzinfo=tzi) for t in zip(yr,mon,day,hr,min,sec,msec)]
        
    if bceaction == 'return':
        return res,bcemask
    else:
        return res
    

def gregorian_to_jd(gtime,utcoffset=None):
    """
    Convert gregorian to julian date
    
    the input `gtime` can either be a sequence (yr,month,day,[hr,min,sec]), 
    where each element may be  or a 
    datetime.datetime object
    
    if datetime objects are given, and utcoffset is None, values are
    converted to UTC based on the datetime.tzinfo objects (if present).  If 
    utcoffset is a string, it is taken to be a timezone name that will be used
    to convert all the gregorian dates to UTC (requires dateutil package).  If 
    it is a scalar, it is taken to be the hour offset of the timezone to convert
    to UTC. 
    
    Adapted from xidl  jdcnv.pro
    """
    from datetime import datetime,date
    
    if isinstance(gtime,datetime) or isinstance(gtime,date):
        datetimes = [gtime]
        scalarout = True
    elif all([isinstance(gt,datetime) for gt in gtime]):
        datetimes = gtime
        scalarout = False
    else:
        datetimes = None
        gtime = list(gtime)
        if not (3 <= len(gtime) < 7):
            raise ValueError('gtime input sequence is invalid size')
        while len(gtime) < 6:
            gtime.append(np.zeros_like(gtime[-1]))
        yr,month,day,hr,min,sec = gtime
        scalarout = False #already a scalar form
        
    if datetimes is not None:
        yr,month,day,hr,min,sec = [],[],[],[],[],[]
        for dt in datetimes:
            if isinstance(dt,date):
                dt = datetime(dt.year,dt.month,dt.day)
            
            if utcoffset is None:
                off = dt.utcoffset()
                if off is not None:
                    dt = dt - off
            yr.append(dt.year)
            month.append(dt.month)
            day.append(dt.day)
            hr.append(dt.hour)
            min.append(dt.minute)
            sec.append(dt.second+dt.microsecond/1e6)
                
                
    
    yr = np.array(yr,dtype='int64',copy=False)
    month = np.array(month,dtype='int64',copy=False)
    day = np.array(day,dtype='int64',copy=False)
    hr = np.array(hr,dtype=float,copy=False)
    min = np.array(min,dtype=float,copy=False)
    sec = np.array(sec,dtype=float,copy=False)
    
    if isinstance(utcoffset,basestring):
        from dateutil import tz
        tzi = tz.gettz(utcoffset)
        
        utcoffset = []
        for t in zip(yr,month,day,hr,min,sec):
            #microsecond from float component of seconds
            dt = datetime(*t,microseconds=int((t[-1]-np.floor(t[-1]))*1e6),tzinfo=tzi)
            utcdt = dt.utcoffset()
            if utcdt is None:
                utcoffset.append(0)
            else:
                utcoffset.append(utcdt.days*24 + (utcdt.seconds + utcdt.microseconds*1e-6)/3600)
        
    
        
#    jdn = (1461 * (yr + 4800 + (month - 14)//12))//4 \
#          + (367 * (month - 2 - 12 * ((month - 14)/12)))//12 \
#          - (3 * ((yr + 4900 + (month - 14)/12)/100))//4  \
#          + day - 32075   
#    res = jdn + (hr-12)/24 + min/1440 + sec/86400
        
    ly = int((month-14)/12)		#In leap years, -1 for Jan, Feb, else 0
    jdn = day - 32075l + 1461l*(yr+4800l+ly)//4
    jdn += 367l*(month - 2-ly*12)//12 - 3*((yr+4900l+ly)//100)//4
    
    res = jdn + (hr/24.0) + min/1440.0 + sec/86400.0 - 0.5
    
    if np.any(utcoffset):
        res -= np.array(utcoffset)/24.0
    
    if scalarout:
        return res[0]
    else:
        return res
    
    
def besselian_epoch_to_jd(bepoch):
    """
    Convert a Besselian epoch to Julian Day, assuming a tropical year of 
    365.242198781 days
    
    :Reference:
    http://www.iau-sofa.rl.ac.uk/2003_0429/sofa/epb.html
    """
    return (bepoch - 1900)*365.242198781 + 2415020.31352

def jd_to_besselian_epoch(jd):
    """
    Convert a Julian Day to a Besselian epoch, assuming a tropical year of 
    365.242198781 days
    
    :Reference:
    http://www.iau-sofa.rl.ac.uk/2003_0429/sofa/epb.html
    """
    return 1900 + (jd - 2415020.31352)/365.242198781

def jd_to_epoch(jd):
    """
    Convert a Julian Day to a Julian Epoch, assuming the year is exactly
    365.25 days long
    
    :Reference:
    http://www.iau-sofa.rl.ac.uk/2003_0429/sofa/epj.html
    """
    return 2000.0 + (jd - 2451545.0)/365.25

def epoch_to_jd(jepoch):
    """
    Convert a Julian Epoch to a Julian Day, assuming the year is exactly
    365.25 days long
    
    :Reference:
    http://www.iau-sofa.rl.ac.uk/2003_0429/sofa/epj.html
    """
    return (jepoch - 2000)*365.25 + 2451545.0
    
    

class Site(object):
    """
    This class represents a location on Earth from which skies are observable.
    
    lat/long are coords.AngularCoordinate objects, altitude in meters
    """
#    tznames = {'EST':-5,'CST':-6,'MST':-7,'PST':-8,
#               'EDT':-4,'CDT':-5,'MDT':-6,'PDT':-7}
    def __init__(self,lat,long,alt=0,tz=None,name=None):
        """
        generate a site by specifying latitude and longitude (as 
        coords.AngularCoordinate objects or initializers for one), optionally
        providing altitude (in meters), time zone (either as a timezone name
        provided by the system or as an offset from UTC), and/or a site name.
        """
        self.latitude = lat
        self.latitude.range = (-90,90)
        self.longitude = long
        self.longitude.range = (-180,180)
        self.altitude = alt
        if tz is None:
            self.tz = self._tzFromLong(self._long)
        elif isinstance(tz,basestring):
            from dateutil import tz  as tzmod
            self.tz = tzmod.gettz(tz)
        else:
            from dateutil import tz as tzmod
            self.tz = tzmod.tzoffset(str(tz),int(tz*60*60))
        if name is None:
            name = 'Default Site'
        self.name = name
        self._currjd = None
    
    @staticmethod
    def _tzFromLong(long):
        from dateutil import tz
        offset =  int(np.round(long.degrees/15))
        return tz.tzoffset(str(offset),offset*60*60)
    
    def _getLatitude(self):
        return self._lat
    def _setLatitude(self,val):
        from .coords import AngularCoordinate
        from operator import isSequenceType
        if isinstance(val,AngularCoordinate):
            self._lat = val
        elif isSequenceType(val) and not isinstance(val,basestring):
            self._lat = AngularCoordinate(*val)
        else:
            self._lat = AngularCoordinate(val)
    latitude = property(_getLatitude,_setLatitude,doc='Latitude of the site in degrees')
    
    def _getLongitude(self):
        return self._long
    def _setLongitude(self,val):
        from .coords import AngularCoordinate
        from operator import isSequenceType
        if isinstance(val,AngularCoordinate):
            self._long = val
        elif isSequenceType(val) and not isinstance(val,basestring):
            self._long = AngularCoordinate(*val)
        else:
            self._long = AngularCoordinate(val)
    longitude = property(_getLongitude,_setLongitude,doc='Longitude of the site in degrees')
    
    def _getAltitude(self):
        return self._alt
    def _setAltitude(self,val):
        if val is None:
            self._alt = None
        else:
            self._alt = float(val)
    altitude = property(_getAltitude,_setAltitude,doc='Altitude of the site in meters')
    
    def _getCurrentobsjd(self):
        if self._currjd is None:
            from datetime import datetime
            return gregorian_to_jd(datetime.utcnow(),utcoffset=None)
        else:
            return self._currjd
    def _setCurrentobsjd(self,val):
        if val is None:
            self._currjd = None
        else:
            if np.isscalar(val):
                self._currjd = val
            else:
                self._currjd = gregorian_to_jd(val)
    currentobsjd = property(_getCurrentobsjd,_setCurrentobsjd,doc="""
    Date and time to use for computing time-dependent values.  If set to None,
    the jd at the instant of calling will be used.  It can also be set as
    datetime objects or (yr,mon,day,hr,min,sec) tuples.
    """)
    
    def localSiderialTime(self,*args,**kwargs):
        """
        compute the local siderial time given an input civil time.
        
        input forms:
        
        * localSiderialTime(): current local siderial time for this Site or uses
                               the value of the :attr:`currentobsjd` property.
        * localSiderialTime(JD): input argument is julian date UTC
        * localSiderialTime(datetime): input argument is a datetime object - if
                                       it has tzinfo, the datetime object's time
                                       zone will be used, otherwise the Site's
        * localSiderialTime(time,day,month,year): input arguments determine 
          local time - time is in hours
        * localSiderialTime(day,month,year,hr,min,sec): local time - hours and
          minutes will be interpreted as integers
        
        
        returns the local siderial time in a format that depends on the 
        `returntype` keyword which can be (default None):
        
        *None/'hours': return LST in decimal hours
        *'string': return LST as a hh:mm:ss.s 
        *'datetime': return a datetime.time object 
        
        guts of calculation adapted from xidl ct2lst.pro
        """
        import datetime
        
        rettype = kwargs.pop('returntype',None)
        if len(kwargs)>0:
            raise TypeError('got unexpected argument '+kwargs.keys()[0])
        if len(args)==0:
            jd = self.currentobsjd
        elif len(args)==1:
            if isinstance(args[0],datetime.datetime):
                if args[0].tzinfo is None:
                    dtobj = datetime.datetime(args[0].year,args[0].month,
                                    args[0].day,args[0].hour,args[0].minute,
                                    args[0].second,args[0].microsecond,self.tz)
                else:
                    dtobj = args[0]
                jd = gregorian_to_jd(dtobj,utcoffset=None)
            else:
                jd = args[0]
        elif len(args) == 4:
            time,day,month,year = args
            hr = np.floor(time)
            min = np.floor(60*(time - hr))
            sec = np.floor(60*(60*(time-hr) - min))
            msec = np.floor(1e6*(60*(60*(time-hr) - min) - sec))
            jd = gregorian_to_jd(datetime.datetime(year,month,day,hr,min,sec,msec,self.tz),utcoffset=None)
        elif len(args) == 6:
            day,month,year,hr,min,sec = args
            msec = 1e6*(sec - np.floor(sec))
            sec = np.floor(sec)
            jd = gregorian_to_jd(datetime.datetime(year,month,day,hr,min,sec,msec,self.tz),utcoffset=None)
        else:
            raise TypeError('invalid number of input arguments')
        
        jd2000 = 2451545.0
        t0 = jd - jd2000
        t = t0//36525 #TODO:check if true-div
        
        #Compute GST in seconds.
        c1,c2,c3,c4 = 280.46061837,360.98564736629,0.000387933,38710000.0
        theta = c1 + (c2 * t0) + t**2*(c3 - t/ c4 )
        
        #Compute LST in hours.
        lst = np.array((theta + self._long.d)/15.0) % 24.0
        
        if lst.shape == tuple():
            lst = lst.ravel()[0]
        
        if rettype is None or rettype == 'hours':
            return lst
        elif rettype == 'string':
            hr = int(lst)
            min = 60*(lst - hr)
            sec = 60*(min - int(min))
            min = int(min)
            return '%i:%i:%f'%(hr,min,sec)
        elif rettype == 'datetime':
            hr = int(lst)
            min = 60*(lst - hr)
            sec = 60*(min - int(min))
            min = int(min)
            msec = int(1e6*(sec-int(sec)))
            sec = int(sec)
            return datetime.time(hr,min,sec,msec)
        else:
            raise ValueError('invallid returntype argument')
        
    def localTime(self,LST=None,date=None):
        """
        computes the local time given a particular value of local siderial time
        and returns it as a datetime.time object.
        
        if `LST` is None, the current local time is returned.  If no date is
        provided the current date is used 
        """
        import datetime,dateutil
        
        if LST is None:
            return datetime.datetime.now().time()
        else:
            if date is None:
                date = datetime.date.today()
        
            ut = LST*15.0-self._long.d
            raise NotImplementedError
            
            
            dt = datetime.datetime(date.year,date.month,date.day,uthr,utmin,utsec,utmsec,dateutil.tz.tzutc())
            return dt.astimezone(self.tz).time()
        
    def apparentPosition(self,coords,datetime=None,setepoch=True):
        """
        computes the positions in horizontal coordinates of an object with the 
        provided fixed coordinates at the requested time(s).
        
        `datetime` can be a sequence of datetime objects or similar representations,
        or it can be a sequnce of JD's.  If None, it uses the current time or 
        the value of the :attr:`currentobsjd` property.
        
        If `setepoch` is True, the position will be precessed to the epoch of 
        the observation
        """
        from .coords import HorizontalPosition
        from operator import isSequenceType
        
        if datetime is None:
            return HorizontalPosition.fromEquatorial(coords,self.localSiderialTime(),self.latitude.d)
        elif hasattr(datetime,'year') or (isSequenceType(datetime) and hasattr(datetime[0],'year')):
            jd = gregorian_to_jd(datetime).ravel()
        else:
            jd = np.array(datetime,copy=False)
        lsts = self.localSiderialTime(jd)
        if setepoch:
            return HorizontalPosition.fromEquatorial(coords,lsts,self.latitude.d,epoch=JD_to_epoch(jd[0]))
        else:
            return HorizontalPosition.fromEquatorial(coords,lsts,self.latitude.d)
        
    def observingTable(self,coord,date=None,strtablename=None,hrrange=(18,6,25)):
        """
        tabulates altitude, azimuth, and airmass values for the provided fixed
        position on a particular date, specified either as a datetime.date 
        object, a (yr,mon,day) tuple, or a julain date (will be rounded to 
        nearest)
        
        if `date` is None, the current date is used
        
        `tab` determines the size of the table - it should be a 3-tuple
        (starthr,endhr,n)
        
        if `strtablename` is True, a string is returned with a printable table 
        of observing data.  If `strtable` is a string, it will be used as the 
        title for the table.  Otherwise, a record array is returned with the 
        hour, alt, az, and airmass
        """        
        from .astropysics import coords
        import datetime
        
        if date is None:
            jd = self.currentobsjd
        elif np.isscalar(date):
            jd = date
        else:
            jd = gregorian_to_jd(date)
            
        date = jd_to_gregorian(jd).date()
        jd0 = np.floor(jd)
        
        starthr,endhr,n = hrrange
        startjd = jd0 + (starthr - 12)/24
        endjd = jd0 + (endhr + 12)/24
        jds = np.linspace(startjd,endjd,n)
        
        timehr = (jds-np.round(np.mean(jds))+.5)*24
        
        
        alt,az = coords.objects_to_coordinate_arrays(self.apparentPosition(coord,jds,setepoch=False))
        z = 90 - alt
        airmass = 1/np.cos(np.radians(z))
        
        ra = np.rec.fromarrays((timehr,alt,az,airmass),names = 'hour,alt,az,airmass')
        if strtablename is not None:
            lines = []
            
            if isinstance(strtablename,basestring):
                lines.append('Object:'+str(strtablename))
            lines.append('{0} {1}'.format(coord.ra.getHmsStr(),coord.dec.getDmsStr()))
            lines.append(str(date))
            lines.append('time\talt\taz\tairmass')
            lines.append('-'*(len(lines[-1])+lines[-1].count('\t')*4))
            for r in ra:
                hr = int(np.floor(r.hour))
                min = int(np.round((r.hour-hr)*60))
                if min==60:
                    hr+=1
                    min = 0
                alt = r.alt
                az = r.az
                am = r.airmass if r.airmass>0 else '...'
                line = '{0:2}:{1:02}\t{2:.3}\t{3:.3}\t{4:.3}'.format(hr,min,alt,az,am)
                lines.append(line)
            return '\n'.join(lines)
        else:
            ra._sitedate = date
            return ra
        
    def observingPlot(self,coords,date=None,names=None,clf=True,plottype='altam',
                           plotkwargs=None):
        """
        generates plots of important observability quantities for the provided
        coordinates.
        
        `coords` should be an :class:`astropysics.coords.LatLongPosition`
        
        `plottype` can be one of:
        
        * 'altam' : a plot of time vs. altitude with a secondary axis for sec(z)
        * 'am' : a plot of time vs. airmass/sec(z)
        * 'altaz': a plot of azimuth vs. altitude
        * 'sky': polar projection of the path on the sky
        
        """
        import matplotlib.pyplot as plt
        from operator import isMappingType
        from .coords import LatLongPosition
        from .plotting import add_mapped_axis
        
        if isinstance(coords,LatLongPosition):
            coords = [coords]
            
        nonames = False
        if names is not None:
            if isinstance(names,basestring):
                names = [names]
            if len(names) != len(coords):
                raise ValueError('names do not match coords')
        else:
            nonames = True
            names = ['' for c in coords]
            
        if isMappingType(plotkwargs):
            plotkwargs = [plotkwargs for c in coords]    
        elif plotkwargs is None:
            plotkwargs = [None for c in coords]
        
        inter = plt.isinteractive()
        try:
            plt.ioff()
            if clf:
                plt.clf()
            oldright = None
            if plottype == 'altam' or plottype == 'alt':   
                if plottype == 'altam':
                    oldright = plt.gcf().subplotpars.right
                    plt.subplots_adjust(right=0.86)
                    
                for n,c,kw in zip(names,coords,plotkwargs):
                    ra = self.observingTable(c,date,hrrange=(0,0,100))
                    if kw is None:
                        plt.plot(ra.hour,ra.alt,label=n)
                    else:
                        kw['label'] = n
                        plt.plot(ra.hour,ra.alt,**kw)
                    
                plt.xlim(0,24)
                
                uppery = plt.ylim()[1]
                plt.ylim(0,uppery)
                
                if not nonames:
                    plt.legend(loc=0)
                
                plt.title(str(ra._sitedate))
                plt.xlabel(r'$\rm hours$')
                plt.ylabel(r'${\rm altitude} [{\rm degrees}]$')
                if plottype == 'altam':
                    yticks = plt.yticks()[0]
                    newticks = list(yticks[1:])
                    newticks.insert(0,(yticks[0]+newticks[0])/2)
                    newticks.insert(0,(yticks[0]+newticks[0])/2)
                    plt.twinx()
                    plt.ylim(0,uppery)
                    plt.yticks(newticks,['%2.2f'%(1/np.cos(np.radians(90-yt))) for yt in newticks])
                    plt.ylabel(r'$\sec(z)$')
                    
                plt.xticks(np.arange(13)*2)
                    
            elif plottype == 'am':
                for n,c,kw in zip(names,coords,plotkwargs):
                    ra = self.observingTable(c,date,hrrange=(0,0,100))
                    
                    ammask = ra.airmass>0
                    if kw is None:
                        plt.plot(ra.hour[ammask],ra.airmass[ammask],label=n)
                    else:
                        kw['label'] = n
                        plt.plot(ra.hour[ammask],ra.airmass[ammask],**kw)
                        
                plt.xlim(0,24)
                plt.xticks(np.arange(13)*2)
                uppery = plt.ylim()[1]
                plt.ylim(1,uppery)
                yticks = list(plt.yticks()[0])
                yticks.insert(0,1)
                plt.yticks(yticks)
                plt.ylim(1,uppery)
                
                plt.title(str(ra._sitedate))
                plt.xlabel(r'$\rm hours$')
                plt.ylabel(r'$airmass / \sec(z)$')
                
                if not nonames:
                    plt.legend(loc=0)
                    
            elif plottype == 'altaz':
                for n,c,kw in zip(names,coords,plotkwargs):
                    ra = self.observingTable(c,date,hrrange=(0,0,100))
                    
                    if kw is None:
                        plt.plot(ra.az,ra.alt,label=n)
                    else:
                        kw['label'] = n
                        plt.plot(ra.az,ra.alt,**kw)
                        
                plt.xlim(0,360)
                plt.xticks(np.arange(9)*360/8)
                
                uppery = plt.ylim()[1]
                plt.ylim(0,uppery)
                
                plt.title(str(ra._sitedate))
                plt.xlabel(r'${\rm azimuth} [{\rm degrees}]$')
                plt.ylabel(r'${\rm altitude} [{\rm degrees}]$')
                
                if not nonames:
                    plt.legend(loc=0)
                
            elif plottype == 'sky':
                for n,c,kw in zip(names,coords,plotkwargs):
                    ra = self.observingTable(c,date,hrrange=(0,0,100))
                    
                    if kw is None:
                        plt.polar(np.radians(ra.az),90-ra.alt,label=n)
                    else:
                        kw['label'] = n
                        plt.polar(np.radians(ra.az),90-ra.alt,**kw)
                        
                plt.ylim(0,90)
                #yticks = plt.yticks()[0]
                yticks = [15,30,45,60,75]
                plt.yticks(yticks,[r'${0}^\circ$'.format(int(90-yt)) for yt in yticks])
                
                plt.title(str(ra._sitedate))
                        
                if not nonames:
                    plt.legend(loc=0)
            else:
                raise ValueError('unrecognized plottype {0}'.format(plottype))
            
            plt.show()
            plt.draw()
            if oldright is not None:
                plt.gcf().subplotpars.right = oldright
        finally:
            plt.interactive(inter)
        
        
        
class Observatory(Site):
    """
    Represents an observatory/Telescope with associated information such as
    platform limits or extinction measurements
    """
    


def __loadobsdb(sitereg):
    from .io import _get_package_data
    obsdb = _get_package_data('obsdb.dat')
    from .coords import AngularCoordinate
    
    obs = None
    for l in obsdb.split('\n'):
        ls = l.strip()
        if len(ls)==0 or ls[0]=='#':
            continue
        k,v = [ss.strip() for ss in l.split('=')]
        if k == 'observatory':
            if obs is not None:
                o = Observatory(lat,long,alt,tz,name)
                sitereg[obs] = o
            obs = v.replace('"','')
            name = long = lat = alt = tz = None
        elif k == 'name':
            name = v.replace('"','')
        elif k == 'longitude':
            vs = v.split(':')
            dec = float(vs[0])
            if len(vs)>1:
                dec += float(vs[1])/60
            #longitudes here are deg W instead of (-180, 180)
            dec*=-1
            if dec <=-180:
                dec += 360
            long = AngularCoordinate(dec)
        elif k == 'latitude':
            vs = v.split(':')
            dec = float(vs[0])
            if len(vs)>1:
                dec += float(vs[1])/60
            lat = AngularCoordinate(dec)
        elif k == 'altitude':
            alt = float(v)
        elif k == 'timezone':
            tz = float(v)
    if obs is not None:
        o = Observatory(lat,long,alt,-1*tz,name)
        sitereg[obs] = o


sites = DataObjectRegistry('sites',Site)
sites['uciobs'] = Observatory(33.63614044191056,-117.83079922199249,80,'PST','UC Irvine Observatory')
__loadobsdb(sites)
#<-----------------Attenuation/Reddening and dust-related---------------------->

class Extinction(PipelineElement):
    """
    This is the base class for extinction-law objects. Extinction laws can be
    passed in as a function to the initializer, or subclasses should override 
    the function f with the preferred law as f(self,lambda), and their 
    initializers should set the zero point
    
    Note that functions are interpreted as magnitude extinction laws ... if 
    optical depth is desired, f should return (-2.5/log(10))*tau(lambda)
    
    A0 is the normalization factor that gets multiplied into the reddening law.
    """
    def  __init__(self,f=None,A0=1):
        if f is not None:
            if not callable(f):
                self.f = f
            else:
                raise ValueError('function must be a callable')
        self.A0 = A0
        
        self._plbuffer = None
    
    def f(self,lamb):
        raise NotImplementedError('must specify an extinction function ')
    
    def __call__(self,*args,**kwargs):
        return self.A0*self.f(*args,**kwargs)
    
    def correctPhotometry(self,mags,band):
        """
        Uses the extinction law to correct a magnitude (or array of magnitudes)
        
        bands is either a string specifying the band, or a wavelength to use
        """
        from .phot import bandwl
        #TODO:better band support
        if isinstance(band,basestring):
            wl = bandwl[band]
        else:
            wl = band
        
        return mags-self(wl)
        
    def Alambda(self,band):
        """
        determines the extinction for this extinction law in a given band or bands
        
        band can be a wavelength or a string specifying a band 
        """
        from operator import isSequenceType
        if isSequenceType(band) and not isinstance(band,basestring):
            return -1*np.array([self.correctPhotometry(0,b) for b in band])
        else:
            return -1*self.correctPhotometry(0,band)
        
    def correctColor(self,colors,bands):
        """
        Uses the supplied extinction law to correct a color (or array of colors)
        where the color is in the specified bands
        
        bands is a length-2 sequence with either a band name or a wavelength for
        the band, or of the form 'bandname1-bandname2' or 'E(band1-band2)'
        """
        
        if isinstance(bands,basestring):
            b1,b2=bands.replace('E(','').replace(')','').split(',')
        else:
            b1,b2=bands
            
        from .phot import bandwl
        #TODO:better band support
        wl1 = bandwl[b1] if isinstance(b1,basestring) else b1
        wl2 = bandwl[b2] if isinstance(b1,basestring) else b2
    
        return colors-self(wl1)+self(wl2)
    
    def correctSpectrum(self,spec,newspec=True):
        """
        Uses the supplied extinction law to correct a spectrum for extinction.
        
        if newspec is True, a copy of the supplied spectrum will have the 
        extinction correction applied
        
        returns the corrected spectrum
        """
    
        if newspec:
            spec = spec.copy()
            
        oldunit = spec.unit
        spec.unit = 'wavelength-angstrom'
        corr = 10**(self(spec.x)/2.5)
        spec.flux *= corr
        spec.err *= corr
        
        spec.unit = oldunit
        return spec
    
    __builtinlines ={
            'Ha':6562.82,
            'Hb':4861.33,
            'Hg':4340.46,
            'Hd':4101.74,
            'He':3970.07
            }
    def correctFlux(self,flux,lamb):
        if isinstance(lamb,basestring) and lamb in Extinction.__builtinlines:
            lamb = Extinction.__builtinlines[lamb]
        return flux*10**(self(lamb)/2.5)
    
    
    __balmerratios={
            'Hab':(2.86,6562.82,4861.33),
            'Hag':(6.16,6562.82,4340.46),
            'Had':(11.21,6562.82,4101.74),
            'Hae':(18.16,6562.82,3970.07),
            'Hbg':(2.15,4861.33,4340.46),
            'Hbd':(3.91,4861.33,4101.74),
            'Hbe':(6.33,4861.33,3970.07),
            'Hgd':(1.82,4340.46,4101.74),
            'Hge':(2.95,4340.46,3970.07),
            'Hde':(1.62,4101.74,3970.07)
            }
    def computeA0FromFluxRatio(self,measured,expected,lambda1=None,lambda2=None,filterfunc=None):
        """
        This derives the normalization of the Extinction function from provided
        ratios for theoretically expected fluxes.  If multiple measurements are
        provided, the mean will be used
        
        measured is the measured line ratio (possibly an array), while expected
        is either the expected line ratios, or a string specifying the
        appropriate balmer flux ratio as "Hab","Hde",etc. (for Halpha/Hbeta or
        Hdelta/Hepsilon) to assume case B recombination fluxes (see e.g. 
        Osterbrock 2007).
        
        lambda1 and lambda2 are the wavelengths for the ratios F1/F2, or None if
        a string is provided 
    
        filterfunc is a function to be applied as the last step - it can 
        either be used to contract an array to (e.g. np.mean), or filter out
        invalid values (e.g. lambda x:x[np.isfinite(x)]).  Default
        does nothing
        
        returns A0,standard deviation of measurements
        """
        if isinstance(expected,basestring):
            R = measured
            balmertuple = Extinction.__balmerratios[expected]
            R0=balmertuple[0]
            lambda1,lambda2=balmertuple[1],balmertuple[2]
        elif isinstance(expected[0],basestring):
            if not np.all([isinstance(e,basestring) for e in expected]):
                raise ValueError('expected must be only transitions or only numerical')
            R0,lambda1,lambda2=[],[],[]
            for e in expected:
                balmertuple = Extinction.__balmerratios[e]
                R0.append(balmertuple[0])
                lambda1.append(balmertuple[1])
                lambda2.append(balmertuple[2])
            R0,lambda1,lambda2=np.array(R0),np.array(lambda1),np.array(lambda2)    
        else:
            if lambda1 and lambda2:
                R,R0 = np.array(measured,copy=False),np.array(expected,copy=False)
                lambda1,lambda2 = np.array(lambda1,copy=False),np.array(lambda2,copy=False)
            else:
                raise ValueError('need to provide wavelengths if not specifying transitions')
        
        A0 = -2.5*np.log10(R/R0)/(self.f(lambda1)-self.f(lambda2))
        
        if filterfunc is None:
            filterfunc = lambda x:x
        self.A0 = A0 = filterfunc(A0)
        return A0,np.std(A0)
    
    #PipelineElement methods
    def _plFeed(self,data,src):
        from .utils import  PipelineError
        from .spec import Spectrum
        if self._plbuffer is None:
            self._plbuffer = {'in':[],'out':[]} 
    
        if isinstance(data,Spectrum):
            self._plbuffer['in'].append(('spec',data))
        else:
            raise PipelineError('unrecognized Extinction correction input data')
        
    def _plProcess(self):
        from .utils import  PipelineError
        if self._plbuffer is None:
            self._plbuffer = {'in':[],'out':[]} 
        
        type,data = self._plbuffer['in'].pop(0)
        try:
            if type=='spec':
                newspec = self.correctSpectrum(data)
                self._plbuffer['out'].append(newspec)
            else:
                assert False,'Impossible point - code error in Extinction pipeline'
        except:
            self.insert(0,spec(type,data))
            
    def _plExtract(self):
        if self._plbuffer is None:
            self._plbuffer = {'in':[],'out':[]} 
            
        if len(self._plbuffer['out']<1):
            return None
        else:
            return self._plbuffer['out'].pop(0)
        
    def _plClear(self):
        self._plbuffer = None
    
class CalzettiExtinction(Extinction):
    """
    This is the average extinction law derived in Calzetti et al. 1994:
    x=1/lambda in mu^-1
    Q(x)=-2.156+1.509*x-0.198*x**2+0.011*x**3
    """
    _poly=np.poly1d((0.011,-0.198,1.509,-2.156)) 
    def __init__(self,A0=1):
        super(CalzettiExtinction,self).__init__(A0=A0)
        
    def f(self,lamb):
        return (-2.5/np.log(10))*self._poly(1e4/lamb)
    
class _EBmVExtinction(Extinction):
    """
    Base class for Extinction classes that get normalization from E(B-V)
    """
    from .phot import bandwl
    __lambdaV=bandwl['V']
    del bandwl
    
    def __init__(self,EBmV=1,Rv=3.1):
        super(_EBmVExtinction,self).__init__(f=None,A0=1)
        self.Rv=Rv
        self.EBmV=EBmV
    
    def _getEBmV(self):
        return self.A0*self.f(self.__lambdaV)/self.Rv
    def _setEBmV(self,val):
        Av=self.Rv*val
        self.A0=Av/self.f(self.__lambdaV)
    EBmV = property(_getEBmV,_setEBmV)
    
    def f(self,lamb):
        raise NotImplementedError
    
class FMExtinction(_EBmVExtinction):
    """
    Base class for Extinction classes that use the form from 
    Fitzpatrick & Massa 90
    """
    
    def __init__(self,C1,C2,C3,C4,x0,gamma,EBmV=1,Rv=3.1):
        self.x0 = x0
        self.gamma = gamma
        self.C1 = C1
        self.C2 = C2
        self.C3 = C3
        self.C4 = C4
        
        super(FMExtinction,self).__init__(EBmV=EBmV,Rv=Rv)
        
    def f(self,lamb):
        x=1e4/np.array(lamb,copy=False)
        C1,C2,C3,C4 = self.C1,self.C2,self.C3,self.C4
        gamma,x0 = self.gamma,self.x0
        
        xsq=x*x
        D=xsq*((xsq-x0*x0)**2+xsq*gamma*gamma)**-2
        FMf=C1+C2*x+C3*D
        
        if np.isscalar(FMf):
            if x>=5.9:
                FMf+=C4*(0.5392*(x-5.9)**2+0.05644*(x-5.9)**3)
        else:
            C4m=x>=5.9
            FMf[C4m]+=C4*(0.5392*(x[C4m]-5.9)**2+0.05644*(x[C4m]-5.9)**3)
        
        return FMf+self.Rv #EBmV is the normalization and is multiplied in at the end
    
class CardelliExtinction(_EBmVExtinction):
    """
    Milky Way Extinction law from Cardelli et al. 1989
    """
    def f(self,lamb):
        scalar=np.isscalar(lamb)
        x=1e4/np.atleast_1d(lamb) #CCM x is 1/microns
        a,b=np.ndarray(x.shape,x.dtype),np.ndarray(x.shape,x.dtype)
        
        if any((x<0.3)|(10<x)):
            raise ValueError('some wavelengths outside CCM 89 extinction curve range')
        
        irs=(0.3 <= x) & (x <= 1.1)
        opts = (1.1 <= x) & (x <= 3.3)
        nuv1s = (3.3 <= x) & (x <= 5.9)
        nuv2s = (5.9 <= x) & (x <= 8)
        fuvs = (8 <= x) & (x <= 10)
        
        #TODO:pre-compute polys
        
        #CCM Infrared
        a[irs]=.574*x[irs]**1.61
        b[irs]=-0.527*x[irs]**1.61
        
        #CCM NIR/optical
        a[opts]=np.polyval((.32999,-.7753,.01979,.72085,-.02427,-.50447,.17699,1),x[opts]-1.82)
        b[opts]=np.polyval((-2.09002,5.3026,-.62251,-5.38434,1.07233,2.28305,1.41338,0),x[opts]-1.82)
        
        #CCM NUV
        y=x[nuv1s]-5.9
        Fa=-.04473*y**2-.009779*y**3
        Fb=-.2130*y**2-.1207*y**3
        a[nuv1s]=1.752-.316*x[nuv1s]-0.104/((x[nuv1s]-4.67)**2+.341)+Fa
        b[nuv1s]=-3.09+1.825*x[nuv1s]+1.206/((x[nuv1s]-4.62)**2+.263)+Fb
        
        a[nuv2s]=1.752-.316*x[nuv2s]-0.104/((x[nuv2s]-4.67)**2+.341)
        b[nuv2s]=-3.09+1.825*x[nuv2s]+1.206/((x[nuv2s]-4.62)**2+.263)
        
        #CCM FUV
        a[fuvs]=np.polyval((-.070,.137,-.628,-1.073),x[fuvs]-8)
        b[fuvs]=np.polyval((.374,-.42,4.257,13.67),x[fuvs]-8)
        
        AloAv = a+b/self.Rv
        
        if scalar:
            return AloAv[0]
        else:
            return AloAv
    
class LMCExtinction(FMExtinction):
    """
    LMC Extinction law from Gordon et al. 2003 LMC Average Sample
    """
    def __init__(self,EBmV=.3,Rv=3.41):
        super(LMCExtinction,self).__init__(-.890,0.998,2.719,0.400,4.579,0.934,EBmV,Rv)
    
class SMCExtinction(FMExtinction):
    """
    SMC Extinction law from Gordon et al. 2003 SMC Bar Sample
    """
    def __init__(self,EBmV=.2,Rv=2.74):
        super(SMCExtinction,self).__init__(-4.959,2.264,0.389,0.461,4.6,1,EBmV,Rv)

def get_SFD_dust(long,lat,dustmap='ebv',interpolate=True):
    """
    Gets map values from Schlegel, Finkbeiner, and Davis 1998 extinction maps
    
    dustmap can either be a filename (if '%s' appears in the string, it will be
    replaced with 'ngp' or 'sgp'), or one of:
        i100: 100-micron map in MJy/Sr
        x   : X-map, temperature-correction factor
        t   : Temperature map in degrees Kelvin for n=2 emissivity
        ebv : E(B-V) in magnitudes
        mask: Mask values
    (in which case the files are assumed to lie in the current directory)
    
    input coordinates are in degrees of galactic latiude and logitude - they can
    be scalars or arrays
    
    if interpolate is an integer, it can be used to specify the order of the
    interpolating polynomial
    """
    from numpy import sin,cos,round,isscalar,array,ndarray,ones_like
    from pyfits import open
    
    if type(dustmap) is not str:
        raise ValueError('dustmap is not a string')
    dml=dustmap.lower()
    if dml == 'ebv' or dml == 'eb-v' or dml == 'e(b-v)' :
        dustmapfn='SFD_dust_4096_%s.fits'
    elif dml == 'i100':
        dustmapfn='SFD_i100_4096_%s.fits'
    elif dml == 'x':
        dustmapfn='SFD_xmap_%s.fits'
    elif dml == 't':
        dustmapfn='SFD_temp_%s.fits'
    elif dml == 'mask':
        dustmapfn='SFD_mask_4096_%s.fits'
    else:
        dustmapfn=dustmap
    
    if isscalar(long):
        l=array([long])*pi/180
    else:
        l=array(long)*pi/180
    if isscalar(lat):
        b=array([lat])*pi/180
    else:
        b=array(lat)*pi/180
        
    if not len(l)==len(b):
        raise ValueError('input coordinate arrays are of different length')
    
    
    
    if '%s' not in dustmapfn:
        f=open(dustmapfn)
        try:
            mapds=[f[0].data]
        finally:
            f.close()
        assert mapds[-1].shape[0] == mapds[-1].shape[1],'map dimensions not equal - incorrect map file?'
        
        polename=dustmapfn.split('.')[0].split('_')[-1].lower()
        if polename=='ngp':
            n=[1]
            if sum(b > 0) > 0:
                print 'using ngp file when lat < 0 present... put %s wherever "ngp" or "sgp" should go in filename'
        elif polename=='sgp':
            n=[-1]
            if sum(b < 0) > 0:
                print 'using sgp file when lat > 0 present... put %s wherever "ngp" or "sgp" should go in filename'
        else:
            raise ValueError("couldn't determine South/North from filename - should have 'sgp' or 'ngp in it somewhere")
        masks = [ones_like(b).astype(bool)]
    else: #need to do things seperately for north and south files
        nmask = b >= 0
        smask = ~nmask
        
        masks = [nmask,smask]
        ns = [1,-1]
        
        mapds=[]
        f=open(dustmapfn%'ngp')
        try:
            mapds.append(f[0].data)
        finally:
            f.close()
        assert mapds[-1].shape[0] == mapds[-1].shape[1],'map dimensions not equal - incorrect map file?'
        f=open(dustmapfn%'sgp')
        try:
            mapds.append(f[0].data)
        finally:
            f.close()
        assert mapds[-1].shape[0] == mapds[-1].shape[1],'map dimensions not equal - incorrect map file?'
    
    retvals=[]
    for n,mapd,m in zip(ns,mapds,masks):
        #project from galactic longitude/latitude to lambert pixels (see SFD98)
        npix=mapd.shape[0]
        
        x=npix/2*cos(l[m])*(1-n*sin(b[m]))**0.5+npix/2-0.5
        y=-npix/2*n*sin(l[m])*(1-n*sin(b[m]))**0.5+npix/2-0.5
        #now remap indecies - numpy arrays have y and x convention switched from SFD98 appendix
        x,y=y,x
        
        if interpolate:
            from scipy.ndimage import map_coordinates
            if type(interpolate) is int:
                retvals.append(map_coordinates(mapd,[x,y],order=interpolate))
            else:
                retvals.append(map_coordinates(mapd,[x,y]))
        else:
            x=round(x).astype(int)
            y=round(y).astype(int)
            retvals.append(mapd[x,y])
            
            
    
        
    if isscalar(long) or isscalar(lat):
        for r in retvals:
            if len(r)>0:
                return r[0]
        assert False,'None of the return value arrays were populated - incorrect inputs?'
    else:
        #now recombine the possibly two arrays from above into one that looks like  the original
        retval=ndarray(l.shape)
        for m,val in zip(masks,retvals):
            retval[m] = val
        return retval
        
    
def get_dust_radec(ra,dec,dustmap,interpolate=True):
    from .coords import equatorial_to_galactic
    l,b = equatorial_to_galactic(ra,dec)
    return get_SFD_dust(l,b,dustmap,interpolate)


  
#DEPRECATED!
def extinction_correction(lineflux,linewl,EBmV,Rv=3.1,exttype='MW'):
    """
    
    Extinction correct a la Cardelli et al 89 from the supplied line data and
    a given E(B-V) along the sightline 
    
    inputs may be numpy arrays
    
    linewl is in angstroms, lineflux in erg s^-1 cm^-2
    
    if the input lineflux is None (or NaN but NOT False or 0) , Alambda is returned instead
    """
    from numpy import array,logical_and,logical_or,polyval,log10,isscalar,where
    from .phot import bandwl
    
    from warnings import warn
    warn('extinction_correction function is deprecated - use Extinction class instead',DeprecationWarning)
    
    if exttype=='LMC':
        eo = LMCExtinction(EBmV=EBmV,Rv=Rv)
        return eo.correctFlux(lineflux,linewl)
    elif exttype == 'SMC':
        eo = SMCExtinction(EBmV=EBmV,Rv=Rv)
        return eo.correctFlux(lineflux,linewl)
    
    if isinstance(linewl,basestring):
        linewl=bandwl[linewl]
        
    if lineflux is None or lineflux is False:
        lineflux=np.nan
        
    
    lineflux=np.atleast_1d(lineflux).astype(float)
    linewl=np.atleast_1d(linewl)
    EBmV=np.atleast_1d(EBmV)
    n=np.max((lineflux.size,linewl.size,EBmV.size))
    
    if n!=1:
        if lineflux.size == 1:
            lineflux = np.ones(n)*lineflux[0]
        elif lineflux.size != n:
            raise ValueError("lineflux is incorrect length")
        if linewl.size == 1:
            linewl = np.ones(n)*linewl[0]
        elif linewl.size != n:
            raise ValueError("linewl is incorrect length")
        if EBmV.size == 1:
            EBmV = np.ones(n)*EBmV[0]
        elif EBmV.size != n:
            raise ValueError("EBmV is incorrect length")
        
    x=1e4/linewl #CCM x is 1/microns
    
    a=array(x)
    b=array(x)
    
    if any(logical_or(x<0.3,10<x)):
        raise ValueError('some wavelengths outside CCM 89 extinction curve range')
    
    irs=where(logical_and(0.3 <= x,x <= 1.1))
    opts=where(logical_and(1.1 <= x,x <= 3.3))
    nuv1s=where(logical_and(3.3 <= x,x <= 5.9))
    nuv2s=where(logical_and(5.9 <= x,x <= 8))
    fuvs=where(logical_and(8 <= x,x <= 10))
    
    #CCM Infrared
    a[irs]=.574*x[irs]**1.61
    b[irs]=-0.527*x[irs]**1.61
    
    #CCM NIR/optical
    a[opts]=polyval((.32999,-.7753,.01979,.72085,-.02427,-.50447,.17699,1),x[opts]-1.82)
    b[opts]=polyval((-2.09002,5.3026,-.62251,-5.38434,1.07233,2.28305,1.41338,0),x[opts]-1.82)
    
    #CCM NUV
    y=x[nuv1s]-5.9
    Fa=-.04473*y**2-.009779*y**3
    Fb=-.2130*y**2-.1207*y**3
    a[nuv1s]=1.752-.316*x[nuv1s]-0.104/((x[nuv1s]-4.67)**2+.341)+Fa
    b[nuv1s]=-3.09+1.825*x[nuv1s]+1.206/((x[nuv1s]-4.62)**2+.263)+Fb
    
    a[nuv2s]=1.752-.316*x[nuv2s]-0.104/((x[nuv2s]-4.67)**2+.341)
    b[nuv2s]=-3.09+1.825*x[nuv2s]+1.206/((x[nuv2s]-4.62)**2+.263)
    
    #CCM FUV
    a[fuvs]=polyval((-.070,.137,-.628,-1.073),x[fuvs]-8)
    b[fuvs]=polyval((.374,-.42,4.257,13.67),x[fuvs]-8)
    
    AloAv=a+b/Rv #Al/Av
    Al=AloAv*Rv*EBmV #from Rv=Av/E(B-V)
    
    
    finalval=Al
    magi= ~np.isnan(lineflux)
    realmag=-2.5*log10(lineflux[magi])-Al[magi]
    finalval[magi]=10**(realmag/-2.5)
    
    if n==1:
        return finalval[0]
    else:
        return finalval
        
#DEPRECATED!
def extinction_from_flux_ratio(frobs,frexpect,outlambda=None,Rv=3.1,tol=1e-4):
    """
    frobs is the observed flux ratio f1/f2
    
    frexpect is either a string code specifying a hydrogen transition
    (e.g. 'Hab' is Halpha/Hbeta, 'Hde' is Hdelta/Hepsilon, from Ostriker 2E)    
    or a tuple of the form (expected f1/f2,lambda1,lambda2) wl in angstroms
    
    outputs E(B-V) to a tolerance specified by tol if outlambda is 0/False/None,
    otherwise outputs Alambda (tol still determines E(B-V)) (outlambda can be
    UBVRI or ugriz as from B&M)
    
    frobs can be an array, but other values cannot
    """
    from scipy.optimize import fmin
    
    from warnings import warn
    warn('extinction_from_flux_ratio function is deprecated - use Extinct class instead',DeprecationWarning)
    
    scalarout=np.isscalar(frobs)
    
    frobs=np.atleast_1d(frobs)
    
    hd={
    'Hab':(2.86,6562.82,4861.33),
    'Hag':(6.16,6562.82,4340.46),
    'Had':(11.21,6562.82,4101.74),
    'Hae':(18.16,6562.82,3970.07),
    'Hbg':(2.15,4861.33,4340.46),
    'Hbd':(3.91,4861.33,4101.74),
    'Hbe':(6.33,4861.33,3970.07),
    'Hgd':(1.82,4340.46,4101.74),
    'Hge':(2.95,4340.46,3970.07),
    'Hde':(1.62,4101.74,3970.07)
    }
    if isinstance(frexpect,basestring):
        frexpect=hd[frexpect]
    
    fr0,l1,l2=frexpect
    
    A2mA1=-2.5*np.log10(fr0/frobs)
    
    fres = lambda x,Y: np.abs(Y - (extinction_correction(None,l2,x,Rv)-extinction_correction(None,l1,x,Rv)))
    
    EBmV=np.ndarray(A2mA1.shape)
    EBmVr=EBmV.ravel()
    for i,A in enumerate(A2mA1.ravel()):
        EBmVr[i]=fmin(fres,0,args=(A,),xtol=tol,disp=0)[0]
        
    if scalarout:
        EBmV=EBmV[0]
        
    if outlambda:
        if isinstance(outlambda,basestring):
            from .phot import bandwl
            outlambda=bandwl[outlambda]
        return extinction_correction(None,outlambda,EBmV,Rv)
    else:
        return EBmV
    
