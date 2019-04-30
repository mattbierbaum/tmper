import os
import time
import shutil
import requests
import unittest
import multiprocessing
import subprocess
import tempfile
from datetime import datetime, timedelta
from urllib.parse import urljoin
from contextlib import contextmanager

import tmper.web
import tmper.util

ADDR = '127.0.0.1'
PORT = 3333
URL = os.environ.get('TMPER_TEST_SERVER', 'http://{}:{}'.format(ADDR, PORT))
SERVE_PATH = '/tmp/tmpertest'
WORKING_PATH = os.path.join(SERVE_PATH, 'work')

lorem = """Unde earum dolores commodi qui. Et consequatur tenetur numquam
dolorem voluptas. Nesciunt expedita eos molestiae. Vel minus sequi et
voluptatum.  Repellat culpa voluptatem eligendi est corporis. Dignissimos et
alias sed nihil voluptatem sint qui."""


class FlaskRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.check_call(['mkdir', '-p', SERVE_PATH])
        subprocess.check_call(['mkdir', '-p', WORKING_PATH])
        os.chdir(WORKING_PATH)

        cls.proc = multiprocessing.Process(target=tmper.web.serve, args=(SERVE_PATH, PORT, ADDR))
        cls.proc.start()

        date_start = datetime.now()
        while True:
            time.sleep(0.2)

            if datetime.now() - date_start > timedelta(seconds=10):
                raise RuntimeError("Waited 10 sec for server to start, aborting")

            try:
                r = requests.get(URL)
            except IOError as e:
                continue

            if r.status_code == 200:
                break

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        shutil.rmtree(SERVE_PATH)

    @contextmanager
    def tempfile(self):
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(lorem)
            f.flush()
            f.seek(0)
            yield f

    def upload(self, **kwargs):
        with self.tempfile() as f:
            return tmper.util.upload(URL, f.name, **kwargs)

    def download(self, code, **kwargs):
        filename = tmper.util.download(URL, code, **kwargs)
        with open(filename) as f:
            return f.read()

    def test_01_upload_no_options(self):
        code = self.upload()

        response = requests.get(urljoin(URL, code))
        r, s = response.content, response.status_code
        self.assertEqual(s, 200)
        self.assertEqual(r.decode('utf-8'), lorem)

    def test_02_download_no_options(self):
        code = self.upload()
        out = self.download(code)
        self.assertEqual(out, lorem)

    def test_03_updown_with_key_error(self):
        key = 'secretpassword'

        code = self.upload(password=key)
        with self.assertRaises(KeyError):
            out = self.download(code, password='')

        out = self.download(code, password=key)
        self.assertEqual(out, lorem)

    def test_04_updown_with_key(self):
        key = 'secretpassword'

        code = self.upload(password=key)
        out = self.download(code, password=key)
        self.assertEqual(out, lorem)

    def test_05_counts(self):
        code = self.upload(num=2)

        out = self.download(code)
        self.assertEqual(out, lorem)

        out = self.download(code)
        self.assertEqual(out, lorem)

        with self.assertRaises(KeyError):
            out = self.download(code)

        #self.assertDictEqual(expected_result, r)
        #self.assertEqual(s, status.HTTP_200_OK)
        #self.assertEqual(s, status.HTTP_406_NOT_ACCEPTABLE)
        #self.assertTrue('reason' in r)
