#!/usr/bin/env python2
# -*- coding: utf-8 -*-
'''sporteasy_sync

Usage:
  sporteasy_sync --login LOGIN --password PASSWORD
  sporteasy_sync --no-download
 
Options:
  -h --help
  -l --login Login
  -p --password Password
  -d --no-download
'''

import os

import atexit
import dateparser
import datetime
import dateutil.relativedelta
import docopt
import json
import locale
import lxml
import lxml.etree
import lxml.html.html5parser
import pyjq
import selenium.webdriver
import sets
import string
import tempfile
import time
import unicodecsv
import warnings


# List of calendars
calendars = [
    {
        'name': 'regionale 2 homme',
        'type': 'regional2',
        'url': 'calendarlist/2017-2018/regionale-2-10905579'
    },
    {
        'name': 'regionale femme',
        'type': 'regional_women',
        'url': 'calendarlist/2017-2018/regionale-femmes'
    },
    {
        'name': 'maîtres',
        'type': 'master',
        'url': 'calendarlist/2017-2018/championnat-maitre'
    },
    {
        'name': 'tournois',
        'type': 'tournament',
        'url': 'calendarlist/2017-2018/tournament'
    },
    {
        'name': '',
        'type': 'all',
        'url': 'calendarlist/2017-2018/all'
    }
]

def get_calendar_filename(calendar):
    '''Return filename of a calendar'''
    return os.path.join(tempfile.gettempdir(), calendar['type'])

def download_calendars(args):
    '''Download calendars'''

    # Open browser
    browser = selenium.webdriver.PhantomJS()
    atexit.register(lambda: browser.close())
    
    # Login to sporteasy
    browser.get('https://www.sporteasy.net/en/login/')
    username = browser.find_element_by_id("id_username")
    password = browser.find_element_by_id("id_password")
    username.send_keys(args['--login'])
    password.send_keys(args['--password'])
    browser.find_element_by_id("login_form").submit()
    
    # Dump calendar data
    base_url = 'https://amns-waterpolo.sporteasy.net'
    for calendar in calendars:
        url = base_url + '/' + calendar['url']
        browser.get(url)
        filename = get_calendar_filename(calendar) + '.xml'
        with open(filename, 'w') as file:
            file.write(browser.page_source.encode('utf-8'))

def load_events():
    ids = sets.Set()
    events = []
    for calendar in calendars:
        # Load file
        filename = get_calendar_filename(calendar) + '.xml'
        tree = lxml.html.html5parser.parse(filename)
        #print(lxml.etree.tostring(tree, pretty_print=True))
        
        # Get events
        type = calendar['type']
        name = calendar['name']
        
        for el in tree.iterfind('//*[@data-event-id]'):
            #print(lxml.etree.tostring(el, pretty_print=True))
            #print(lxml.etree.tostring(el.find('.//*[@class = "date"]//*')[0], pretty_print=True))
            
            # Find event identifier
            id = el.xpath('string(*[@class = "type_numbers"]//@href)').strip()
            if id in ids:
                continue
            else:
                ids.add(id)
            
            # Fill event
            event = {}
            event['id'] = id
            event['type'] = type
            event['name'] = name
            date_string = el.xpath('*[@class = "date"]//*/text()')[0].strip()
            if date_string:
                date = dateparser.parse(' '.join(date_string.split(' ')[1:]))
                if date.month < 9:
                    date += dateutil.relativedelta.relativedelta(years=+1)
                event['date'] = str(date)
            type_numbers = el.xpath('*[@class = "type_numbers"]//*/text()')
            if type_numbers:
                event['type_numbers'] = type_numbers[0].strip()
            left_hand = el.xpath('*[starts-with(@class, "left_hand")]//*/text()')
            if left_hand:
                event['left_hand'] = left_hand[0].strip()
            right_hand = el.xpath('*[starts-with(@class, "right_hand")]//*/text()')
            if right_hand:
                event['right_hand'] = right_hand[0].strip()
            not_sportive = el.xpath('*[@class = "not_sportive"]//*/text()')
            if not_sportive:
                event['not_sportive'] = not_sportive[0].strip()
            
            # Append event
            events.append(event)
    
    return events

def dump_events_to_cvs(events):
    '''Dumps events into .csv files'''
    for calendar in calendars:
        filename = get_calendar_filename(calendar) + '.csv'
        with open(filename, 'wb') as csvfile:
            # Create .csv file
            field_names = [u'Type', u'Journée', u'Date', u'Heure du match', u'Domicile', u'Extérieur']
            writer = unicodecsv.DictWriter(csvfile, fieldnames=field_names, delimiter=';')
            writer.writeheader()
            
             # Select events by type
            if calendar['type'] == 'all':
                selected_events = events
            else:
                selected_events = pyjq.all('.|map( select(.type == "%s") )' % (calendar['type']), events)[0]
            #print json.dumps(selected_events, indent=2)
            
            # Sort events by date
            for event in selected_events:
                date = datetime.datetime.strptime(event['date'], '%Y-%m-%d %H:%M:%S') if 'date' in event else None
                event[u'date'] = date
            sorted_events = sorted(selected_events, key=lambda item: item.get('date') if item.get('date') else datetime.datetime(2999, 1, 1))
            
            # Writes events
            capitalized_name = string.capwords(calendar['name'])
            for event in sorted_events:
                not_sportive = event['not_sportive'] if 'not_sportive' in event else None
                date = event['date'] if 'date' in event else None
                writer.writerow(
                    {
                        u'Type': string.capwords(event['name']),
                        u'Journée': not_sportive if not_sportive else event['type_numbers'][1:] if 'type_numbers' in event else None,
                        u'Date': date.strftime('%A %d %B %Y') if date else None,
                        u'Heure du match': date.strftime('%Hh%M') if date else None,
                        u'Domicile': event['left_hand'] if 'left_hand' in event else None,
                        u'Extérieur': event['right_hand'] if 'right_hand' in event else None,
                    }
                )

     
if __name__ == "__main__":
    args = docopt.docopt(__doc__, version='0.1')
    
    # Hide warnings
    warnings.filterwarnings("ignore")
    
    # Set locale
    locale.setlocale(locale.LC_TIME, "fr_FR")
    
    # Download calendars
    if not args['--no-download']:
        download_calendars(args)
    
    # Loads events
    events = load_events()
    
    # Dump events
    dump_events_to_cvs(events)
