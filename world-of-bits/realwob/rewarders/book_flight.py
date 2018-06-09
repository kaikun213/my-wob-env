import random
import re
import logging

from realwob.rewarders.utils import choose_one
from realwob.rewarders import (WebImitateRewarder, get_flow_url, parse_webform,
                               log_warn, log_info)

_west_coast_cities = [
    'San Francisco', 'Seattle', 'Los Angeles', 'San Diego'
]

_east_coast_cities = [
    'New York', 'Boston', 'Pittsburg'
]

_flight_type = [
    'return', 'one-way'
]

def _make_flight_instruction():
    data = dict(
        dep_city = choose_one(_west_coast_cities),
        dest_city = choose_one(_east_coast_cities),
        dep_month = 5,
        dest_month = 5,
        dep_day = choose_one(range(10, 20)),
        dest_day = choose_one(range(20, 31)),
        flight_type = choose_one(_flight_type)
    )
    if data['flight_type'] == 'return':
        return ('Search for a %(flight_type)s flight from %(dep_city)s to %(dest_city)s departing on %(dep_month)s'
                '/%(dep_day)s and returning on %(dest_month)s/%(dest_day)s' % data)
    else:
        return ('Search for a %(flight_type)s flight from %(dep_city)s to %(dest_city)s departing on %(dep_month)s'
                '/%(dep_day)s' % data)


def FlightRewarderTemplate(target_urls, target_method='POST'):
    class FlightRewarder(WebImitateRewarder):
        def __init__(self, db_path, mode='DATA'):
            super(FlightRewarder, self).__init__(db_path, mode)

        def requests_of_interest(self, flow):
            url = get_flow_url(flow)

            # trigger RoI.
            if flow.request.method == target_method and url in target_urls:
                log_warn('[RoI] triggered %s == %s', url, str(target_urls))
                form = parse_webform(flow)
                self.done()
                log_warn('[RoI] parsed form = %s', str(form))
                return [form]

            # nothing is triggered.
            return []

        def reset(self):
            super(FlightRewarder, self).reset()
            self._instruction = _make_flight_instruction()

    return FlightRewarder

UnitedRewarder = FlightRewarderTemplate(['mobile.united.com/Booking', 'mobile.united.com/Booking/OneWaySearch'])
DeltaRewarder = FlightRewarderTemplate(['m.delta.com/mwsb/service/itinerarySearch'])
AlaskaRewarder = FlightRewarderTemplate(['m.alaskaair.com/shopping/flights'])
JetblueRewarder = FlightRewarderTemplate(['https://mobile.jetblue.com/mt/book.jetblue.com/shop/search/', 'mobile.jetblue.com/mt/book.jetblue.com/shop/search/'])
DeltaRewarder = FlightRewarderTemplate(['m.delta.com/mwsb/service/itinerarySearch'])
VirginAmericaRewarder = FlightRewarderTemplate(['www.virginamerica.com/api/v2/booking/search'])

class AARewarder(FlightRewarderTemplate(['www.aa.com/booking/find-flights'])):
    def __init__(self, db_path, mode='DATA'):
        super(AARewarder, self).__init__(db_path, mode)

    def requests_of_interest(self, flow):
        forms = super(AARewarder, self).requests_of_interest(flow)
        new_forms = []
        for form in forms:
            new_forms.append({k : v for (k, v) in form.items() if k.decode('utf-8') in
                        ['segments[0].travelDate', 'segments[1].travelDate',
                         'passengerCount', 'roundTrip', 'segments[0].destination',
                         'segments[0].origin']
                    })
        return new_forms

class KayakRewarder(WebImitateRewarder):
    def __init__(self, db_path, mode='DATA'):
        super(KayakRewarder, self).__init__(db_path, mode)

    def requests_of_interest(self, flow):
        url = get_flow_url(flow)

        forms = []
        if flow.request.method == 'GET':

            match_return_ticket = re.match(r'www.kayak.com/(?:[a-z]*/)?flights/([^\/]*)/([^\/]*)/([^\/]*)', url)
            if match_return_ticket:
                (route, dep_date, return_date) = match_return_ticket.groups()
                (dep_airport, arr_airport) = route.split('-')
                forms.append({
                    'dep-airport': dep_airport,
                    'arr-airport': arr_airport,
                    'dep-date': dep_date,
                    'return-date': return_date
                })

            match_oneway_ticket = re.match(r'www.kayak.com/(?:[a-z]*/)?flights/([^\/]*)/([^\/]*)', url)
            if match_oneway_ticket:
                print(match_oneway_ticket.groups())
                (route, dep_date) = match_oneway_ticket.groups()
                (dep_airport, arr_airport) = route.split('-')
                forms.append({
                    'dep-airport': dep_airport,
                    'arr-airport': arr_airport,
                    'dep-date': dep_date,
                })

            if forms:
                self.done()
                log_warn('[RoI] parsed form = %s', str(forms))

        return forms

    def reset(self):
        super(KayakRewarder, self).reset()
        self._instruction = _make_flight_instruction()



