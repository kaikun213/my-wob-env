import os

from backend.signup.server import SignupMockServer
import backend.iphone.server

global_registry = {}


global_registry['wob.mini.CharacterExp-v0'] = 'http://localhost/miniwob/a-character.html'
global_registry['wob.mini.AnEasyExperiment-v0'] = 'http://localhost/miniwob/an-experiment-easy.html'
global_registry['wob.mini.AnExperiment-v0'] = 'http://localhost/miniwob/an-experiment.html'
global_registry['wob.mini.BisectAngle-v0'] = 'http://localhost/miniwob/bisect-angle.html'
global_registry['wob.mini.BookFlight-v0'] = 'http://localhost/miniwob/book-flight.html'
global_registry['wob.mini.ChaseCircle-v0'] = 'http://localhost/miniwob/chase-circle.html'
global_registry['wob.mini.ChooseDate-v0'] = 'http://localhost/miniwob/choose-date.html'
global_registry['wob.mini.ChooseList-v0'] = 'http://localhost/miniwob/choose-list.html'
global_registry['wob.mini.CircleCenter-v0'] = 'http://localhost/miniwob/circle-center.html'
global_registry['wob.mini.ClickButton-v0'] = 'http://localhost/miniwob/click-button.html'
global_registry['wob.mini.ClickButtonSequence-v0'] = 'http://localhost/miniwob/click-button-sequence.html'
global_registry['wob.mini.ClickCheckboxes-v0'] = 'http://localhost/miniwob/click-checkboxes.html'
global_registry['wob.mini.ClickCollapsible-v0'] = 'http://localhost/miniwob/click-collapsible.html'
global_registry['wob.mini.ClickCollapsible2-v0'] = 'http://localhost/miniwob/click-collapsible-2.html'
global_registry['wob.mini.ClickColor-v0'] = 'http://localhost/miniwob/click-color.html'
global_registry['wob.mini.ClickDialog-v0'] = 'http://localhost/miniwob/click-dialog.html'
global_registry['wob.mini.ClickDialog2-v0'] = 'http://localhost/miniwob/click-dialog-2.html'
global_registry['wob.mini.ClickLink-v0'] = 'http://localhost/miniwob/click-link.html'
global_registry['wob.mini.ClickMenu-v0'] = 'http://localhost/miniwob/click-menu.html'
global_registry['wob.mini.ClickMenu2-v0'] = 'http://localhost/miniwob/click-menu-2.html'
global_registry['wob.mini.ClickOption-v0'] = 'http://localhost/miniwob/click-option.html'
global_registry['wob.mini.ClickPie-v0'] = 'http://localhost/miniwob/click-pie.html'
global_registry['wob.mini.ClickScrollList-v0'] = 'http://localhost/miniwob/click-scroll-list.html'
global_registry['wob.mini.ClickShades-v0'] = 'http://localhost/miniwob/click-shades.html'
global_registry['wob.mini.ClickShape-v0'] = 'http://localhost/miniwob/click-shape.html'
global_registry['wob.mini.ClickTab-v0'] = 'http://localhost/miniwob/click-tab.html'
global_registry['wob.mini.ClickTab2-v0'] = 'http://localhost/miniwob/click-tab-2.html'
global_registry['wob.mini.ClickTest-v0'] = 'http://localhost/miniwob/click-test.html'
global_registry['wob.mini.ClickTest2-v0'] = 'http://localhost/miniwob/click-test-2.html'
global_registry['wob.mini.ClickWidget-v0'] = 'http://localhost/miniwob/click-widget.html'
global_registry['wob.mini.CopyPaste-v0'] = 'http://localhost/miniwob/copy-paste.html'
global_registry['wob.mini.CopyPaste2-v0'] = 'http://localhost/miniwob/copy-paste-2.html'
global_registry['wob.mini.CountShape-v0'] = 'http://localhost/miniwob/count-shape.html'
global_registry['wob.mini.CountSides-v0'] = 'http://localhost/miniwob/count-sides.html'
global_registry['wob.mini.DragBox-v0'] = 'http://localhost/miniwob/drag-box.html'
global_registry['wob.mini.DragCube-v0'] = 'http://localhost/miniwob/drag-cube.html'
global_registry['wob.mini.DragItem-v0'] = 'http://localhost/miniwob/drag-item.html'
global_registry['wob.mini.DragItems-v0'] = 'http://localhost/miniwob/drag-items.html'
global_registry['wob.mini.DragItemsGrid-v0'] = 'http://localhost/miniwob/drag-items-grid.html'
global_registry['wob.mini.DragShapes-v0'] = 'http://localhost/miniwob/drag-shapes.html'
global_registry['wob.mini.DragSortNumbers-v0'] = 'http://localhost/miniwob/drag-sort-numbers.html'
global_registry['wob.mini.EmailInbox-v0'] = 'http://localhost/miniwob/email-inbox.html'
global_registry['wob.mini.EnterDate-v0'] = 'http://localhost/miniwob/enter-date.html'
global_registry['wob.mini.EnterPassword-v0'] = 'http://localhost/miniwob/enter-password.html'
global_registry['wob.mini.EnterText-v0'] = 'http://localhost/miniwob/enter-text.html'
global_registry['wob.mini.EnterText2-v0'] = 'http://localhost/miniwob/enter-text-2.html'
global_registry['wob.mini.EnterTextDynamic-v0'] = 'http://localhost/miniwob/enter-text-dynamic.html'
global_registry['wob.mini.EnterTime-v0'] = 'http://localhost/miniwob/enter-time.html'
global_registry['wob.mini.FindMidpoint-v0'] = 'http://localhost/miniwob/find-midpoint.html'
global_registry['wob.mini.FindWord-v0'] = 'http://localhost/miniwob/find-word.html'
global_registry['wob.mini.FocusText-v0'] = 'http://localhost/miniwob/focus-text.html'
global_registry['wob.mini.FocusText2-v0'] = 'http://localhost/miniwob/focus-text-2.html'
global_registry['wob.mini.GridCoordinate-v0'] = 'http://localhost/miniwob/grid-coordinate.html'
global_registry['wob.mini.GuessNumber-v0'] = 'http://localhost/miniwob/guess-number.html'
global_registry['wob.mini.HighlightText-v0'] = 'http://localhost/miniwob/highlight-text.html'
global_registry['wob.mini.HighlightText2-v0'] = 'http://localhost/miniwob/highlight-text-2.html'
global_registry['wob.mini.IdentifyShape-v0'] = 'http://localhost/miniwob/identify-shape.html'
global_registry['wob.mini.LoginUser-v0'] = 'http://localhost/miniwob/login-user.html'
global_registry['wob.mini.MovingItems-v0'] = 'http://localhost/miniwob/moving-items.html'
global_registry['wob.mini.NavigateTree-v0'] = 'http://localhost/miniwob/navigate-tree.html'
global_registry['wob.mini.NumberCheckboxes-v0'] = 'http://localhost/miniwob/number-checkboxes.html'
global_registry['wob.mini.ReadTable-v0'] = 'http://localhost/miniwob/read-table.html'
global_registry['wob.mini.ReadTable2-v0'] = 'http://localhost/miniwob/read-table-2.html'
global_registry['wob.mini.ResizeTextarea-v0'] = 'http://localhost/miniwob/resize-textarea.html'
global_registry['wob.mini.RightAngle-v0'] = 'http://localhost/miniwob/right-angle.html'
global_registry['wob.mini.ScrollText-v0'] = 'http://localhost/miniwob/scroll-text.html'
global_registry['wob.mini.ScrollText2-v0'] = 'http://localhost/miniwob/scroll-text-2.html'
global_registry['wob.mini.SearchEngine-v0'] = 'http://localhost/miniwob/search-engine.html'
global_registry['wob.mini.SimonSays-v0'] = 'http://localhost/miniwob/simon-says.html'
global_registry['wob.mini.SimpleAlgebra-v0'] = 'http://localhost/miniwob/simple-algebra.html'
global_registry['wob.mini.SimpleArithmetic-v0'] = 'http://localhost/miniwob/simple-arithmetic.html'
global_registry['wob.mini.SocialMedia-v0'] = 'http://localhost/miniwob/social-media.html'
global_registry['wob.mini.Terminal-v0'] = 'http://localhost/miniwob/terminal.html'
global_registry['wob.mini.TextEditor-v0'] = 'http://localhost/miniwob/text-editor.html'
global_registry['wob.mini.TextTransform-v0'] = 'http://localhost/miniwob/text-transform.html'
global_registry['wob.mini.TicTacToe-v0'] = 'http://localhost/miniwob/tic-tac-toe.html'
global_registry['wob.mini.UseAutocomplete-v0'] = 'http://localhost/miniwob/use-autocomplete.html'
global_registry['wob.mini.UseColorwheel-v0'] = 'http://localhost/miniwob/use-colorwheel.html'
global_registry['wob.mini.UseColorwheel2-v0'] = 'http://localhost/miniwob/use-colorwheel-2.html'
global_registry['wob.mini.UseSlider-v0'] = 'http://localhost/miniwob/use-slider.html'
global_registry['wob.mini.UseSlider2-v0'] = 'http://localhost/miniwob/use-slider-2.html'
global_registry['wob.mini.UseSpinner-v0'] = 'http://localhost/miniwob/use-spinner.html'
global_registry['wob.mini.VisualAddition-v0'] = 'http://localhost/miniwob/visual-addition.html'

# ------------------------ RealWoB Environments ---------------------------
db_root = '/tmp/demo/realwob/db'
WEBDRIVER_DEVICES = {
    'Apple iPhone 6': {
        "deviceMetrics": { "width": 375, "height": 667, "pixelRatio": 1.0 , "touch": True },
        "userAgent": "Mozilla/5.0 (Linux; Android 4.2.1; en-us; Nexus 5 Build/JOP40D) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19"
    }
}

import realwob.rewarders

# - SignUp
import realwob.rewarders.signup as signup

signup_config = {}
for _id in range(20):
    def signup_entry_local_scope():
        local_id = _id
        cache_db_path = 'signup.{}'.format(local_id)
        rewarder_db_path = 'signup.{}'.format(local_id)
        return {
            'type': 'realwob',
            'www': 'https://openai.github.io/signup-forms/{}/'.format(local_id),
            'db': cache_db_path,
            'rewarder': lambda mode: signup.SignUpRewarderTemplate(local_id)(rewarder_db_path, mode),
            'device': 'Apple iPhone 6',
            'reload': True
        }

    global_registry['wob.real.SignUp-{}-v0'.format(_id)] = signup_entry_local_scope()


global_registry['wob.iPhone-EnterText-v0'] = {
    'type': 'mockwob',
    'www': 'static/iphone/enter-text',
    'server': backend.iphone.server.EnterTextServer
}

# - Book Flight
import realwob.rewarders.book_flight as book_flight

flight_booking_config = {
    'United': {
        'entry': 'https://mobile.united.com/',
        'rewarder': book_flight.UnitedRewarder
    },
    'Delta': {
        'entry': 'https://m.delta.com/?p=homeScreen',
        'rewarder': book_flight.DeltaRewarder
    },
    'Alaska': {
        'entry': 'https://m.alaskaair.com/',
        'rewarder': book_flight.AlaskaRewarder
    },
    'Jetblue': {
        'entry': 'https://mobile.jetblue.com/mt/book.jetblue.com/shop/search/',
        'rewarder': book_flight.JetblueRewarder
    },
    'VirginAmerica': {
        'entry': 'https://www.virginamerica.com/',
        'rewarder': book_flight.VirginAmericaRewarder
    },
    'AA': {
        'entry': 'https://www.aa.com/booking/find-flights',
        'rewarder': book_flight.AARewarder
    },
    'Kayak': {
        'entry': 'https://www.kayak.com/flights',
        'rewarder': book_flight.KayakRewarder
    },
}

for name, config in flight_booking_config.items():
    # create a local variable scope for reward factory.
    def flight_entry_local_scope():
        cache_db_path = 'flight.{}'.format(name)
        rewarder_db_path = 'flight.{}'.format(name)
        _config = config
        return {
            'type': 'realwob',
            'www': _config['entry'],
            'db': cache_db_path,
            'rewarder': lambda mode: _config['rewarder'](rewarder_db_path, mode),
            'device': 'Apple iPhone 6',
            'reload': True
        }

    global_registry['wob.real.BookFlight-{}-v0'.format(name)] = flight_entry_local_scope()

# - Quizlet
import realwob.rewarders.quizlet as quizlet

quizlet_learn_config = {
    'Geography': {
        'id': '94527189'
    },
    'Planet': {
        'id': '118298426'
    },
    'Universe-Small': {
        'id': '159104219'
    },
    'Universe': {
        'id': '74019381'
    },
    'Comet': {
        'id': '59553915'
    },
    'Moon': {
        'id': '162092329'
    },
    'Mars': {
        'id': '42961113'
    },
    'Solar-System': {
        'id': '77980043'
    }
}

for task in ['Learn', 'Test']:
    for name, config in quizlet_learn_config.items():
        # create a local variable scope for reward factory.
        def quizlet_entry_local_scope():
            cache_db_path = 'quizlet.{}.{}'.format(name, task)
            _config = config

            if task == 'Learn':
                Rewarder = quizlet.QuizletLearnRewarder
            elif task == 'Test':
                Rewarder = None

            return {
                'type': 'realwob',
                'www': 'https://quizlet.com/' + _config['id'] + '/{}'.format(task.lower()),
                'db': cache_db_path,
                'rewarder': quizlet.QuizletLearnRewarder,
                'device': 'Apple iPhone 6',
                'reload': True
            }

        global_registry['wob.real.Quizlet-{}-{}-v0'.format(name, task)] = quizlet_entry_local_scope()

# - Duolingo
duolingo_config = {
    'French-Basic-1': {
        'path': 'fr/Basics-1/1'
    }
}

for name, config in duolingo_config.items():
    # create a local variable scope for reward factory.
    def duolingo_entry_local_scope():
        cache_db_path = 'duolingo.{}'.format(name)
        _config = config

        return {
            'type': 'realwob',
            'www': 'https://www.4tests.com/exam/sat/1/',
            'db': cache_db_path,
            'rewarder': None,
            'device': 'Apple iPhone 6',
            'reload': True
        }

    global_registry['wob.real.Duolingo-{}-v0'.format(name)] = duolingo_entry_local_scope()


# - Map Apps
maps_config = {
    'Google': {
        'entry': 'https://www.google.com/maps/@37.4231682,-122.1689283'
    },
    'Bing': {
        'entry': 'https://www.bing.com/maps/'
    },
    'Here': {
        'entry': 'https://mobile.here.com'
    },
    'OSM': {
        'entry': 'http://www.openstreetmap.org/'
    }
}

for name, config in maps_config.items():
    # create a local variable scope for reward factory.
    def maps_entry_local_scope():
        cache_db_path = 'maps.{}'.format(name)
        _config = config

        return {
            'type': 'realwob',
            'www': _config['entry'],
            'db': cache_db_path,
            'rewarder': None,
            'device': 'Apple iPhone 6',
            'reload': True
        }

    global_registry['wob.real.Maps-{}-v0'.format(name)] = maps_entry_local_scope()


# - Shopping Apps
ecommerce_config = {
    'Amazon': {
        'entry': 'https://www.amazon.com/'
    },
    'eBay': {
        'entry': 'http://m.ebay.com/'
    },
    'Instacart': {
        'entry': 'https://www.instacart.com/?guided_signup=0'
    },
    'Alibaba': {
        'entry': 'https://m.alibaba.com/'
    }
}

for name, config in ecommerce_config.items():
    def ecommerce_entry_local_scope():
        cache_db_path = 'shopping.{}'.format(name)
        _config = config

        return {
            'type': 'realwob',
            'www': _config['entry'],
            'db': cache_db_path,
            'rewarder': None,
            'device': 'Apple iPhone 6',
            'reload': True
        }

    global_registry['wob.real.Shopping-{}-v0'.format(name)] = ecommerce_entry_local_scope()


# - Music Players
music_player_config = {
    'Spotify': {
        'entry': 'https://open.spotify.com/embed?uri=spotify%3Auser%3Atianlinshi%3Aplaylist%3A1quFARtEbcwvvGxWZougMt'
    },
}

for name, config in music_player_config.items():
    def music_player_entry_local_scope():
        cache_db_path = 'music.{}'.format(name)
        _config = config

        return {
            'type': 'realwob',
            'www': _config['entry'],
            'db': cache_db_path,
            'rewarder': None,
            'device': 'Apple iPhone 6',
            'reload': True
        }

    global_registry['wob.real.Music-{}-v0'.format(name)] = music_player_entry_local_scope()

# ---------------- Auxiliary RealWoB Tasks  --------------------------------------
# realWoB button clicking.
click_button_sites = {
    'Airfrance': 'https://mobile.airfrance.us/US/en/local/process/standardbooking/BookNewTripAction.do',
    'Craigslist': 'https://sfbay.craigslist.org/sfc/',
    'Chase': 'https://www.chase.com/',
    # sites that do not work.
    'CNN': 'http://www.cnn.com/?refresh=0' # times out.
}

click_button_selectors = {
    'Airfrance': 'a.bmw-bloc-btn',
    'Craigslist': 'div.col:nth-of-type(n+2) h4.ban a',
    'CNN': 'div.nav-flyout__menu-item:nth-of-type(n+2) a.nav-flyout__section-title',
    'Chase': 'div.sidemenu__menu__section:nth-of-type(2) p.sidemenu__menu__section--primary--link__title',
}

js_sleep = lambda milliseconds:  'var start = new Date().getTime(); while(true) {if ((new Date().getTime() - start) > %d) break;};' % milliseconds
click_button_prescript = {
    'CNN': "document.querySelector('#menu').click(); ", # click on the menu.
    'Chase': "document.querySelector('#skip-sidemenu').click();"
}

for name, url in click_button_sites.items():
    def rewarder_factory_scope():
        css_selector = click_button_selectors.get(name, 'button')
        prescript = click_button_prescript.get(name, '')
        return lambda mode: realwob.rewarders.DOMClickButtonRewarder(selector=css_selector,
                                                                        prescript=prescript)

    global_registry['wob.real.ClickButton-%s-v0' % name] = {
        'type': 'realwob',
        'www': url,
        'db': 'flight.{}'.format(name),
        'rewarder': rewarder_factory_scope(),
        'device': 'Apple iPhone 6',
        'reload': True
    }
