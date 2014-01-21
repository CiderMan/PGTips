import re

class ptError(Exception):
    pass

class ptParseError(ptError):
    pass

class ptValidationError(ptError):
    pass

class ptNotImplementedError(ptError):
    pass

_ymd_sep = re.compile(
    "^(?P<year>[0-9]{4})"   # Year
    "(?P<sep>[:-])"         # Seperator (compulsory - the nosep case will catch the case where there is only a year)
    "(?P<month>[0-9]{1,2})" # Month (compulsory)
    "((?P=sep)"             # The same seperator (optional)
     "(?P<day>[0-9]{1,2})"  # Day (if there was a seperator)
    ")?$")
_ymd_nosep = re.compile(
    "^(?P<year>[0-9]{4})"   # Year
    "((?P<month>[0-9]{2})"  # Month (optional)
    "(?P<day>[0-9]{2}))?$") # Day (compulsory if there was a month but no seperators)
_ywd_sep = re.compile(
    "^(?P<year>[0-9]{4})"   # Year
    "(?P<sep>[:-]?)"        # Seperator (optional)
    "[wW](?P<week>[0-9]{1,2})" # Week (compulsory)
    "((?P=sep)"             # The same seperator (optional)
     "(?P<weekday>[0-9])"   # Day (of week) (if there was a seperator)
    ")?$")
_yord = re.compile(
    "^(?P<year>[0-9]{4})"     # Year
    "(?P<sep>[:-])?"          # Seperator (optional)
    "(?P<ordinal>[0-9]{3})$") # Ordinal (compulsory)
_yshort = re.compile(
    "^(?P<year>[0-9]{1,3})$") # Year (shortened to indicate decade, century or millenium)

def split_date(date):
    dateFields = ["year", "month", "week", "day", "weekday", "ordinal"]
    formats = [_ymd_sep, _ymd_nosep, _ywd_sep, _yord, _yshort]

    results = filter(lambda m: bool(m),
                     map(lambda expr: expr.match(date),
                         formats))

    if len(results) != 1:
        raise ptParseError(date)

    result = results[0]

    retVal = {}
    for field in dateFields:
        try:
            retVal[field] = result.group(field)
        except IndexError:
            retVal[field] = None

    return retVal

_time = re.compile(
    "^(?P<hour>[0-9]{2})"     # Hour
    "((?P<sep>[:-]?)"         # Seperator (optional)
     "(?P<minutes>[0-9]{2})"  # Minutes (compulsory if seperator)
     "((?P=sep)"              # Seperator (optional)
      "(?P<seconds>[0-9]{2})" # Seconds (compulsory if seperator)
     ")?"
    ")?"
    "([.,](?P<partial>[0-9]+))?") # Fractional (only valid on the least significant unit)

_tz = re.compile(
    "^(?P<tzhours>[-+][0-9]{2})"
    "([:-]?(?P<tzminutes>[0-9]{2}))?$")

def split_time(time):
    timeFields = ["hour", "minutes", "seconds", "partial", "tzhours", "tzminutes"]
    formats = [_time]

    results = filter(lambda m: bool(m),
                     map(lambda expr: expr.match(time),
                         formats))

    if len(results) != 1:
        raise ptParseError(time)

    result = results[0]

    retVal = {}
    for field in timeFields:
        try:
            retVal[field] = result.group(field)
        except IndexError:
            retVal[field] = None

    tz = time[result.end():].strip()
    if tz != "":
        if tz.upper() == "Z":
            retVal["tzhours"] = "Z"
        else:
            m = _tz.match(tz.strip())

            if not m:
                raise ptParseError(tz)
            else:
                retVal["tzhours"] = m.group("tzhours")
                retVal["tzminutes"] = m.group("tzminutes")
    
    return retVal

def split_datetime(dateTime):
    print "test:", dateTime
    
    def _split_at_first(string, sepList):
        def min_index(x, y):
            if x < 0:
                return y
            elif y < 0:
                return x
            else:
                return min(x, y)
        splitPoint = reduce(min_index, map(string.find, sepList), -1)
        if splitPoint < 0:
            return string, None
        else:
            return string[:splitPoint], string[splitPoint+1:]
    
    date, time = _split_at_first(dateTime, "T ")
    if time is None:
        raise ptParseError("No date/time seperator")

    d = split_date(date.strip())
    map(lambda x: d.setdefault(x[0], x[1]), split_time(time.strip()).iteritems())

    return d

_validators = [
    # Year has a full range but may only be a decade, century or millenium
    # specifier so we have to leave it as a string
    ("month", int, 1, 12),
    ("week", int, 1, 53),
    ("day", int, 1, 31),
    ("weekday", int, 1, 7),
    ("hour", int, 0, 24),
    ("minutes", int, 0, 59),
    ("seconds", int, 0, 60),
    # Partial need not be validated
    # Tzhours needs special validation
    ("tzminutes", int, 0, 59),
    ]

def validate_datetime(dt):
    for item, convertor, minVal, maxVal in _validators:
        if dt[item] is not None:
            v = convertor(dt[item])
            if v < minVal or v > maxVal:
                raise ptValidationError(dt[item] + " is not a valid " + item)
            dt[item] = v
    return dt

if __name__ == "__main__":
    teststrings =[
        "2011:01:22 17:51:36+00:00",
        "2010:09:02 16:29:47",
        "2010:09 16:29:47",
        "2010 16:29:47",
        "20T16:29:47",
        "2010:9:2 16:29:47",
        "2009-08-28T19:11:37Z",
        "2009W082T19:11:37Z",
        "2009128T19:11:37Z",
        "2009-W08-2T19:11:37Z",
        "2009-128T19:11:37Z",
        ]
    from itertools import imap
    for r in imap(validate_datetime, imap(split_datetime, teststrings)):
        if r["week"] is not None:
            print "Week", r["week"], "Day", r["weekday"], "of", r["year"]
        elif r["ordinal"] is not None:
            print "Day", r["ordinal"], "of", r["year"]
        else:
            print r["year"], r["month"], r["day"]
        print r
    
    
