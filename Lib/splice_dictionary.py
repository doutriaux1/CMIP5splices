"""@package splice_dictionary

@mainpage Documentation for the splice_dictionary package
@author Kate Marvel
@author Charles Doutriaux
@date 2013



"""

import genutil
import os
import numpy as np
import fnmatch
from datetime import datetime
import cdms2 as cdms
from string import upper,lower
import collections
import cdtime
defaultTemplate = "%(root)%(experiment)/%(realm)/%(time_frequency)/%(variable)/cmip5.%(model).%(experiment).%(rip).%(time_frequency).%(realm).%(tableid).%(variable).%(version).%(latest).xml"
def locate(pattern, root=os.curdir):
    '''Locate all files matching supplied filename pattern in and below
    supplied root directory.'''
    for path, dirs, files in os.walk(os.path.abspath(root)):
        files = [os.path.join(path,f) for f in files]
        for filename in fnmatch.filter(files, pattern):
            yield filename

def parse_filename(fname):
    '''Parse the full path+filename.  Return a dictionary whose keys are model metadata.'''
    try:
        
        root,work,cmip,experiment,realm,mo_new,variable,filename = fname.split("/")
        if len(filename.split(".")) == 11:
            cmip,model,experiment,rip,mo,realm,tableid,variable,version,latest,ext = filename.split(".")
        else:
           cmip,model,experiment,rip,mo,realm,tableid,variable,version,ext = filename.split(".") 
           latest = "??"
    except:

        print "filename must be of the form %s" % defaultTemplate
        raise TypeError
    d = {}
    d["root"]="/".join([root,work,cmip,""])
    d["experiment"] = experiment
    d["realm"] = realm
    d["variable"] = variable
    d["model"] = model
    d["rip"] = rip
    d["version"] = version
    d["time_frequency"] = mo_new
    d["tableid"] = tableid
    d["latest"]= latest
    return d

def newest_version(listoffiles):
    """Get the newest version of the xml according to Jeff Painter's instructions."""
    if type(listoffiles) is not type([]):
        return listoffiles
    if len(listoffiles)==1:
        return listoffiles[0]
    versions = np.array([x.split("ver-")[1].split(".")[0] for x in listoffiles])
    d = parse_filename(listoffiles[0])
    model = d["model"]
    version_numbers = [x.split("v")[-1] for x in versions]
    for i in range(len(version_numbers)):
        try:
            version_numbers[i] = float(version_numbers[i])
        except:
            version_numbers[i] = 1.
    if upper(model) == "CSIRO":
        less_than_1000 = np.where(np.array(version_numbers <1000.))
        I = np.argmax(version_numbers[less_than_1000])
    else:
         I = np.argmax(version_numbers)
         
    return listoffiles[I]
    
    

def check_parentage(fname):
    """Returns either the parent file or list of strings with errors"""
    d = parse_filename(fname)
    openf = cdms.open(fname)
    keys = openf.attributes.keys()
    flags = []
    if "realization" not in keys:
        flags+[ "no realization specified"]
        meta_r="NA"
    else:
        meta_r = str(openf.attributes["realization"])


    if "initialization_method" not in keys:
        flags+=[ "no initialization specified"]
        meta_i="NA"
    else:
        meta_i = str(openf.attributes["initialization_method"])
    if "physics_version" not in keys:
        flags+=["no physics version specified"]
        meta_p = "NA"
    else:
        meta_p = str(openf.attributes["physics_version"])

    meta_rip = "r"+meta_r+"i"+meta_i+"p"+meta_p

    if "parent_experiment_rip" not in keys:
        flags+=["parent_experiment_rip not specified"]
        parent_rip="NA"
    else:
        parent_rip = openf.attributes["parent_experiment_rip"]

    if meta_rip != d["rip"]:
        flags+=["model rip ("+d["rip"]+") and metadata rip ("+meta_rip+") do not match"]

    if meta_rip != parent_rip:
        flags+=["metadata rip ("+meta_rip+") and parent rip ("+parent_rip+") do not match"] 

    if "parent_experiment" not in openf.attributes.keys():
        flags+=["no parent experiment specified"]
        parent = "NA"
    else:    
        parent = openf.attributes["parent_experiment"]
        if lower(parent) != "historical":
            flags+=["parent experiment is "+parent]
      
    if "branch_time" not in openf.attributes.keys():
        flags +=["branch time not specified"]
    
        

    d["experiment"] = "historical"
    d["version"] = "*"
    files = list(find_files(d))

    if len(files)==0:
        flags+=["parent file not found in "+d["root"]]
    else:
        historical = newest_version(files)
        bf = branch_flag(fname,historical)
        if bf is not None:
            flags += bf
   
    if len(flags)==0:
        return historical
    else:
        return flags
        
            
        

def find_files(d,print_search_string = False,template=defaultTemplate):
    '''Return all datafiles that match criteria specified in the dictionary d'''
    #template = "%(root)%(experiment)/%(realm)/%(time_frequency)/%(variable)/cmip5.%(model).%(experiment).%(rip).mo.%(realm).%(tableid).%(variable).%(version).%(latest).xml"
     
    filename = genutil.StringConstructor(template)
    
    # set defaults
    [setattr(filename,k,"*") for k in filename.keys()]
    # by default root is /work/cmip5/
    filename.root = "/work/cmip5/"

    #set filename attributes
    
    [setattr(filename,k,d[k]) for k in d.keys()]
    if print_search_string:
        print filename()
   #Get most complete specified directory
    

    return locate(filename(),root = filename.root)
    
time = str(datetime.now())
user = os.environ["USER"]
#d = {}
#d[user+" "+time] = {}


def remove_duplicate_versions(listoffiles):
    remove_this = []
    remove_version = lambda x: x.split(".ver")[0]
    files_rv = map(remove_version, listoffiles)
    dcounter = collections.Counter(files_rv)
    duplicates = [n for n, i in dcounter.iteritems() if i > 1]
    for dupe in duplicates:
        
        versions = [listoffiles[x] for x in np.argwhere([x.find(dupe)==0 for x in files_rv])]
        
        nv = newest_version(versions)
        for version in versions:
            if version != nv:
                remove_this +=[version]
    [listoffiles.remove(x) for x in remove_this]
    return listoffiles

def flag(d,latest_version_only = True):
    """Use the check_parentage function to flag files with potential splicing issues.   """
    flagged = {}
    ok = {}
    all_files = find_files(d)
    if latest_version_only:
        all_files = remove_duplicate_versions(list(all_files))
    for f in all_files:
        print f
        parent = check_parentage(f)
        if type(parent)==type([]):
            flagged[f]=parent
        else:
            ok[f] = parent
    return flagged, ok

def compare_flags(flag_a,flag_b):
    """Given two flag dictionaries, check to see if problems arise from same model"""
    keys_a = flag_a.keys()
    keys_b = flag_b.keys()
    mod_rip = lambda keys: set([x.split(".")[1]+"."+x.split(".")[3] for x in keys])
    set_a = mod_rip(keys_a)
    set_b = mod_rip(keys_b)
    df = set_a.symmetric_difference(set_b)
    return set_a.intersection(df), set_b.intersection(df)


def modify_dictionary(rcpfile,histfile = None,fname=None):
    """Removes rcpfile from flagged dictionary and places it in okdictionary"""
    if fname is None:
        fname = "flagged.dict"
    f=open(fname)
    flagged,ok = eval(f.read())
    f.close()
    if rcpfile in flagged.keys():
        problems = flagged.pop(rcpfile)
        if histfile is None:
            d = parse_filename(rcpfile)
            d["version"]="*"
            d["experiment"]="historical"
            histfile = newest_version(list(find_files(d)))
        print "Despite these problems:"
        print problems
        print "File "+rcpfile+" will be spliced with historical file "+histfile
        ok[rcpfile]=histfile
        f=open(fname,'w')
        f.write(repr((flagged,ok)))
        f.close()
    else:
        print rcpfile + " was not flagged!"
    
def move_cesm_to_ok(fname):
    d = {}
    d["model"]="CESM*"
    d["realm"] = "seaIce"
    d["experiment"]="rcp45"
    d["variable"]='sic'
    files = remove_duplicate_versions(find_files(d))
    for rcpfile in files:
        modify_dictionary(rcpfile)




    
def test_branch_time(ok):
    btimes = {}
    startstop={}
    for k in ok.keys():
        
        rcp_file = cdms.open(k)
        
        hist_file = cdms.open(ok[k])
        
        try:
            b = rcp_file.attributes["branch_time"]
        except:
            btimes[k] =  "no branch time "
            continue
        variable = parse_filename(k)["variable"]
        

        historical_time = hist_file[variable].getTime()
        rcp_time = rcp_file[variable].getTime()
        units = hist_file[variable].getTime().units
        newunits = rcp_file[variable].getTime().units
        calendar = hist_file[variable].getTime().getCalendar()
        branch_time = cdtime.relativetime(b,units)
        branch_time_new = cdtime.relativetime(b,newunits)
        
        actual_hist_end_time = historical_time.asComponentTime()[-1]
        actual_rcp_start_time = rcp_time.asComponentTime()[0]
        
        btimes[k]= [branch_time.tocomp(),branch_time_new.tocomp()]
        startstop[k] = [actual_hist_end_time.tocomp(),actual_rcp_start_time.tocomp()]
    return btimes,startstop


def branch_flag(rcp,hist):
    rcp_file = cdms.open(rcp)
        
    hist_file = cdms.open(hist)
    
    variable = parse_filename(rcp)["variable"]
        

    historical_time = hist_file[variable].getTime()
    rcp_time = rcp_file[variable].getTime()
    stop = historical_time.asComponentTime()[-1]
    start = rcp_time.asComponentTime()[0]


    d = parse_filename(rcp)
    model = d["model"]
    
    
    if start.year !=2006:
        if (lower(model).find("had")>=0) and (start.year == 2005):
            flags = None
        else:
            print model 
            flags = ["RCP start time is "+str(start)]
            print flags
    else:
        flags = None

    #Charles Doutriaux add, checking if branch time described in metadata of rcp actually exsit in parent
    #B=rcp_file.branch_time
    #try:
    #    ok = historical_time.mapInterval((B,B,'ccb'))
    #except Exception,err:
    #    print model,B,historical_time,err
    #    if flags is None:
    #        flags = ["RCP branch_time does not exist in parent file"]
    #    else:
    #        flags+=["RCP branch_time does not exist in parent file"]
    #    print flags
    return flags



def pretty_print(flagged,pfile = None):
    """ Print the flagged dictionary in human-readable format to file"""
    if pfile is None:
        pfile = "flags.txt"
    f = open(pfile,"w")
    f.write("MODEL \t \t PROBLEMS\n")
    for bad_rcp in flagged.keys():
        f.write(bad_rcp+"\t \t "+str(flagged[bad_rcp])+"\n")
    f.close()
        

