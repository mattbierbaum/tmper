from __future__ import print_function

import os
import json
import glob
import base64
import string
import random
import itertools
import signal
import bcrypt

import threading
import parsedatetime
import datetime
import dateutil.parser

import tornado.web
import tornado.log
import tornado.ioloop
import tornado.template

import logging
logger = logging.getLogger('tmper')

import pkg_resources
dist = pkg_resources.get_distribution('tmper')

def b64read(path, name):
    return base64.b64encode(open(os.path.join(path, name), 'rb').read())

def _ascii(string):
    return string.encode('ascii', 'xmlcharrefreplace')

def key_hash(key, rounds=5):
    return bcrypt.hashpw(_ascii(key), bcrypt.gensalt(rounds))

def key_check(key, hashed_key):
    return (bcrypt.hashpw(_ascii(key), _ascii(hashed_key)) == _ascii(hashed_key))

def tostring(obj):
    if isinstance(obj, bytes):
        return obj.decode()
    return obj

def tobytes(obj):
    if isinstance(obj, str):
        return obj.encode()
    return obj

#=============================================================================
# web server functions and data
#=============================================================================
# set the root directory for data, by default we should only be working in the
# current directory where this python file lives
CHARS = string.ascii_lowercase + ''.join(map(str, range(10)))

# flexible configuration options
MAX_DOWNLOADS = 3
CODE_LEN = 3

# build the regex used by the app to determine if valid URL
CODE_REGEX = string.Template(r'/([$chars]{$num})?')
CODE_REGEX = CODE_REGEX.substitute(chars=CHARS, num=CODE_LEN)

# decide the template's path, either local of the package global
local = os.path.exists(os.path.join(os.getcwd(), 'templates', 'index.html'))
template_dir = './templates' if local else os.path.join(dist.location, 'templates')

FAVICON = b64read(template_dir, 'favicon.png')
FAVICON2 = b64read(template_dir, 'favicon2.png')

# render most of the webpages right now so they are cached
subs = {'favicon': FAVICON, 'favicon2': FAVICON2, 'codelen': CODE_LEN}
loader = tornado.template.Loader(template_dir)
PAGE_INDEX = loader.load("index.html").generate(**subs)
PAGE_CODE = loader.load("code.html").generate(**subs)
PAGE_HELP = loader.load("help.html").generate(**subs)
PAGE_ERROR = loader.load("error.html").generate(**subs)
PAGE_DOWNLOAD = loader.load("download.html").generate(**subs)

# also need to leave a few pages templated, let's use string.Template for ease
TMPL_CODE = string.Template(tostring(PAGE_CODE))
TMPL_ERROR = string.Template(tostring(PAGE_ERROR))

#=============================================================================
# helper functions that dont directly involve the web responses
#=============================================================================
DEFAULT_ROOT = os.path.join(os.getcwd(), './.tmper-files')

class FileManager(object):
    def __init__(self, root=DEFAULT_ROOT, char=CHARS, clen=CODE_LEN):
        self.char = char
        self.clen = clen
        self.root = root
        self.timers = {}

        self.init()

    def init(self, root=None):
        self.root = root or self.root
        self.cancel_timers()

        if not os.path.exists(self.root):
            os.mkdir(self.root)

        files = glob.glob(os.path.join(self.root, '?'*self.clen))
        self.used_codes = set([
            os.path.basename(f) for f in files
        ])
        self.all_codes = set([
            ''.join(i) for i in itertools.product(*(self.char,)*self.clen)
        ])
        self.start_timer(self.used_codes)

    def start_timer(self, codes):
        """ Takes either single code or list of codes and start timers """
        codes = [codes] if not isinstance(codes, (set, list)) else codes
        for c in codes:
            if c in self.timers:
                continue

            meta = self.open_meta(c)
            time = date2diff(str2date(meta['time']))
            time = max([time, 1])
            self.timers[c] = threading.Timer(time, self.timer_func, args=(c,))
            self.timers[c].start()

    def timer_func(self, code):
        logging.info('deleting {}...'.format(code))
        if self.exists(code):
            self.delete_file(code)

    def cancel_timers(self):
        for code, timer in self.timers.items():
            if timer.isAlive():
                timer.cancel()
        self.timers = {}

    def unique_code(self):
        avail = list(self.all_codes.difference(self.used_codes))
        if len(avail) == 0:
            return None
        return random.choice(avail)

    def path(self, n):
        return os.path.join(self.root, n)

    def pathj(self, n):
        return os.path.join(self.root, '{}.json'.format(n))

    def save_file(self, name, content, meta):
        self.update_file(name, content)
        self.update_meta(name, meta)

        self.start_timer(name)
        self.used_codes.update([name])

    def update_file(self, name, content):
        with open(self.path(name), 'wb') as f:
            f.write(content)

    def update_meta(self, name, meta):
        with open(self.pathj(name), 'w') as f:
            json.dump(meta, f)

    def open_file(self, name):
        data = open(self.path(name)).read()
        meta = open(self.pathj(name)).read()
        return data, json.loads(meta)

    def open_meta(self, name):
        return json.load(open(self.pathj(name)))

    def delete_file(self, name):
        os.remove(self.path(name))
        os.remove(self.pathj(name))

        if name in self.timers:
            timer = self.timers.pop(name)
            if timer.isAlive():
                timer.cancel()

        self.used_codes.remove(name)

    def exists(self, name):
        return os.path.isfile(self.path(name))

def dt2date(dt):
    cal = parsedatetime.Calendar()
    return cal.parseDT(dt, datetime.datetime.now())[0]

def str2date(string):
    return dateutil.parser.parse(string)

def date2diff(date):
    return (date - datetime.datetime.now()).total_seconds()

files = None

def signal_handler(signum, frame):
    logging.info('exiting...')
    files.cancel_timers()
    tornado.ioloop.IOLoop.instance().stop()
    logging.info('done.')

#=============================================================================
# The actual web application now
#=============================================================================
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/help", HelpHandler),
            (r"/error-size", ErrorSizeHandler),
            (r"/download", DownloadHandler),
            (CODE_REGEX, MainHandler)
        ]
        super(Application, self).__init__(
            handlers, default_handler_class=DefaultHandler, gzip=True, debug=False
        )

class Handler(tornado.web.RequestHandler):
    def error(self, text, code=404):
        self.clear()
        self.set_status(code)

        if self.cli():
            self.write(text)
        else:
            text = tostring(text)
            self.write(TMPL_ERROR.substitute(error=text))
        self.finish()

    def cli(self):
        """ Returns true if this URL was visited from the command line """
        agent = self.request.headers.get('User-Agent', '')
        clis = ['curl', 'Wget', 'tmper']
        return any([i in agent for i in clis])

    def cache_headers(self, nhours=24):
        self.set_header('Cache-Control', 'public,max-age=%d' % int(3600*nhours))

class HelpHandler(Handler):
    def get(self):
        self.cache_headers()
        self.write(PAGE_HELP)
        self.finish()

class DownloadHandler(Handler):
    def get(self):
        self.cache_headers()
        self.write(PAGE_DOWNLOAD)
        self.finish()

class DefaultHandler(Handler):
    def prepare(self):
        self.error('404')

    def write_error(self, status_code, **kwargs):
        self.error(status_code, status_code)

class ErrorSizeHandler(Handler):
    def get(self):
        self.error('Filesize > 128MB', 413)

class MainHandler(Handler):
    def prepare(self, *args, **kwargs):
        self.request.connection.set_max_body_size(int(1e8))
        super(MainHandler, self).prepare(*args, **kwargs)

    def serve_file_headers(self, meta):
        self.set_header('Content-Type', meta['content_type'])
        self.set_header(
            'Content-Disposition', 'attachment; filename="{}"'.format(meta['filename'])
        )

    def serve_file(self, data, meta):
        self.serve_file_headers(meta)
        self.write(data)

    def write_formatted(self, data, meta):
        typ = meta['content_type']

        if 'image' in typ:
            # display images directly in browser
            self.write("<img src='data:%s;base64,%s'/>" % (typ, base64.b64encode(data)))
        elif 'text' in typ:
            # display code and text in pre block
            self.write('<pre>%s</pre>' % data)
        else:
            # otherwise, just download the file like usual
            self.serve_file(data, meta)

    def head(self, args):
        if not args:
            args = self.get_arg('code', '')

        if not args:
            self.finish()
        else:
            if not files.exists(args):
                self.error('not found')
                return

            data, meta = files.open_file(args)
            key = self.get_arg('key', '')

            # check the key is present if required
            if meta['key']:
                if not key_check(key, meta['key']):
                    self.error('invalid key')
                    return

            # write out the headers and finish
            self.serve_file_headers(meta)
            self.finish()

    def get(self, args, headonly=False):
        if not args:
            args = self.get_arg('code', '')

        if not args:
            self.cache_headers()
            self.write(PAGE_INDEX)
            self.finish()
        else:
            if not files.exists(args):
                self.error('not found')
                return

            data, meta = files.open_file(args)
            key = self.get_arg('key', '')

            # check the key is present if required
            if meta['key']:
                if not key_check(key, meta['key']):
                    self.error('invalid key')
                    return

            # either delete the file or update the view count in the meta data
            meta['n'] -= 1
            if meta['n'] == 0:
                files.delete_file(args)
            else:
                files.update_meta(args, meta)

            # if we are on command line, just return data, otherwise display it pretty
            if self.cli():
                self.serve_file(data, meta)
            elif 'v' in list(self.request.arguments.keys()):
                self.write_formatted(data, meta)
            else:
                self.serve_file(data, meta)
            self.finish()

    def get_arg(self, key, default):
        val = self.request.arguments.get(key, [default])[0]
        val = tostring(val)
        return val

    def post(self, args):
        meta = {}
        codeonly = self.get_arg('codeonly', None)
        meta['key'] = self.get_arg('key', None)
        usern = int(self.get_arg('n', 1))
        usern = max(min(usern, MAX_DOWNLOADS), 0)
        meta['n'] = usern

        if meta['key']:
            meta['key'] = tostring(key_hash(meta['key']))

        try:
            time = dt2date(self.get_arg('time', '3 days'))
        except Exception as e:
            self.error('invalid time')
            return

        # limit the time between valid parameters
        tmin = dt2date('1 min')
        tmax = dt2date('7 days')
        time = max(tmin, min(tmax, time))
        meta['time'] = time.isoformat()

        # change to error occured since file already exists
        if args and files.exists(args):
            self.error('exists')
            return

        if len(self.request.files) == 1:
            # we have files attached, save each of them to new file names
            name = args or files.unique_code()

            if name is None:
                self.error("no codes available")
                return

            fobj = list(self.request.files.values())[0][0]

            # separate the actual contents from the meta data
            body = fobj.pop('body')
            meta.update(fobj)

            # strip paths from meta name (can't be done on client)
            if 'filename' in meta:
                meta['filename'] = os.path.basename(meta['filename'])

            # write the file and return the accepted name
            files.save_file(name, body, meta)

            if not self.cli() and not codeonly:
                response = TMPL_CODE.substitute(namecode=name)
                self.write(response)
            else:
                self.write(name)
            self.finish()

            return
        elif len(self.request.files) == 0:
            self.error('no file attached')
            return
        else:
            self.error("one file at a time")
            return

def serve(root=None, port='8888', addr='127.0.0.1'):
    global files
    files = FileManager()
    files.init(root)

    tornado.log.enable_pretty_logging()
    app = Application()
    app.listen(port, addr)
    signal.signal(signal.SIGINT, signal_handler)
    tornado.ioloop.IOLoop.instance().start()

