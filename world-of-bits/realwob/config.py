# site-specific exceptions.
# parameters to ignore for requests from given sites.
IGNORE_SITE_PARAMS = {
    'www.booking.com': ['_'],
    'f9cdn.azureedge.net': ['_'], # frontier airlines.
    'm.delta.com': ['sessions', 'serialNumber']
}

IGNORE_URL_PARAMS = {
    'm.delta.com/mwsb/service/itinerarySearch': ['credentials', 'version', 'pax']
}

WHITELIST_URL_PARAMS = {
    'www.aa.com/booking/find-flights': ['tripType', 'segments[0].origin', 'segments[0].destination',
                   'segments[0].travelDate', 'segments[1].travelDate', 'passengerCount',
                   'cabin', '_refundable']
}

# ignore domains.
# some websites use certificate pinning to prevent Man-In-Middle attach.
# this means our cache fails so we should avoid making requests to them.
IGNORE_DOMAINS = set([
    'www.google-analytics.com',
    'dis.us.criteo.com',
    'analytics.twitter.com',
    'us-u.openx.net',
    'cookieu2.veinteractive.com',
    'dsum-sec.casalemedia.com',
    'configusa.veinteractive.com',
    't.co',
    'www.facebook.com',
    'ad.doubleclick.net',
    'servedby.flashtalking.com',
    'nexus.ensighten.com',
    'col.eum-appdynamics.com',
    'pfa.levexis.com',
    'fls.doubleclick.net',
    'rules.atgsvcs.com',
    'sec.levexis.com',
    'apis.google.com',
])
