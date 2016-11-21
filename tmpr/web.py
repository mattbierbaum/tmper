from __future__ import print_function

import os
import json
import base64
import string
import random

import tornado.web
import tornado.ioloop
import tornado.template

import pkg_resources

dist = pkg_resources.get_distribution('tmpr')
#config_file = os.path.join(dist.location, 'production.ini')

#=============================================================================
# web server functions and data
#=============================================================================
# set the root directory for data, by default we should only be working in the
# current directory where this python file lives
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')
CHARS = string.ascii_lowercase + ''.join(map(str, range(10)))

FAVICON = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAABGdBTUEAALGPC/xhBQAAAGBQT"
    "FRFooKnN8jxY5PVM7vvM7zwY5LUN8fxo4KnhInAuX2Py3172oZtSZ/k5ZJjOa7s6pxbP9LyTN"
    "jy66VYVtryo4Vmqoxo57Fit5djvp1lw6Jnzaps17Fu3bNt47Rp6a1csZJmx8KbeAAAAEJJREF"
    "UOMtjEBGVl5cXl5CUkpaRlRWTkxPi5+Xm4mTgYOXhY2YTEBRmGNEK2EcVEKuAiRgFjFRXIEOq"
    "ApZRBSQoAAAJHkuVEmG+EwAAAABJRU5ErkJggg=="
)

subs = {'favicon': FAVICON}
loader = tornado.template.Loader(dist.location)#"./templates")
PAGE_INDEX = loader.load("index.html").generate(**subs)
PAGE_CODE = loader.load("code.html").generate(**subs)
PAGE_HELP = loader.load("help.html").generate(**subs)
PAGE_DOWNLOAD = loader.load("download.html").generate(**subs)

TMPL_CODE = string.Template(PAGE_CODE)

#=============================================================================
# The actual web application now
#=============================================================================
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/help", HelpHandler),
            (r"/download", DownloadHandler),
            (r"/([a-z0-9]{2})?", MainHandler)
        ]
        super(Application, self).__init__(handlers, gzip=True)

class HelpHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(PAGE_HELP)
        self.finish()

class DownloadHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(PAGE_DOWNLOAD)
        self.finish()

class MainHandler(tornado.web.RequestHandler):
    def prepare(self, *args, **kwargs):
        self.request.connection.set_max_body_size(int(1e8))
        super(MainHandler, self).prepare(*args, **kwargs)

    def generate_name(self):
        return ''.join([random.choice(CHARS) for i in range(2)])

    def unique_name(self):
        tries, out = 0, self.generate_name()
        while self.exists(out):
            if tries < len(CHARS)**2:
                raise Exception

            out = self.generate_name()
            tries += 1
        return out

    def path(self, n):
        return os.path.join(ROOT, n)

    def pathj(self, n):
        return os.path.join(ROOT, '{}.json'.format(n))

    def save_file(self, name, content, meta):
        with open(self.path(name), 'w') as f:
            f.write(content)

        with open(self.pathj(name), 'w') as f:
            f.write(json.dumps(meta))

    def open_file(self, name):
        data = open(self.path(name)).read()
        meta = json.loads(open(self.pathj(name)).read())
        return data, meta

    def delete_file(self, name):
        os.remove(self.path(name))
        os.remove(self.pathj(name))

    def exists(self, name):
        return os.path.isfile(self.path(name))

    def error(self, text):
        self.clear()
        self.set_status(404)
        self.write(text)
        self.finish()

    def serve_file_headers(self, meta):
        self.set_header('Content-Type', meta['content_type'])
        self.set_header('Content-Disposition', 'attachment; filename='+meta['filename'])

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

    def get(self, args):
        agent = self.request.headers['User-Agent']

        if not args:
            self.write(PAGE_INDEX)
            self.finish()
        else:
            if not self.exists(args):
                self.error('not found')
                return

            data, meta = self.open_file(args)

            # check the key is present if required
            if meta['key']:
                if not meta['key'] == self.request.arguments.get('key', [''])[0]:
                    self.error('key invalid')
                    return

            # either delete the file or update the view count in the meta data
            meta['n'] -= 1
            if meta['n'] == 0:
                self.delete_file(args)
            else:
                self.save_file(args, data, meta)

            # if we are on command line, just return data, otherwise display it pretty
            if 'curl' in agent or 'Wget' in agent:
                self.serve_file(data, meta)
            elif 'v' in self.request.arguments.keys():
                self.write_formatted(data, meta)
            else:
                self.serve_file(data, meta)
            self.finish()

    def post(self, args):
        meta = {}
        meta['key'] = self.request.arguments.get('key', [None])[0]
        usern = int(self.request.arguments.get('n', [1])[0])
        usern = max(min(usern, 10), 0)
        meta['n'] = usern

        # change to error occured since file already exists
        if args and self.exists(args):
            self.error('exists')
            return

        if len(self.request.files) == 1:
            # we have files attached, save each of them to new file names
            name = args or self.unique_name()
            fobj = self.request.files.values()[0][0]

            # separate the actual contents from the meta data
            body = fobj.pop('body')
            meta.update(fobj)

            # write the file and return the accepted name
            self.save_file(name, body, meta)

            response = TMPL_CODE.substitute(namecode=name)
            self.write(response)
            self.finish()
            return

        self.error('improper payload')

def serve(root=None, port='8888', addr='127.0.0.1'):
    global ROOT

    ROOT = root or ROOT
    if not os.path.exists(ROOT):
        os.mkdir(ROOT)
    
    app = Application()
    app.listen(port, addr)
    tornado.ioloop.IOLoop.instance().start()

