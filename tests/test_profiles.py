"""Installation isolation and fail-closed profiles."""
import argparse
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import stt


class Profiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.args = argparse.Namespace(root=self.tmp.name, project='verify-yet-a', service='yet',
                                       environment='test', url='https://lrs-a.invalid', port=28183, admin='test-admin')
        self.path = stt.initialize(self.args)

    def test_two_independent_compose_models(self):
        a = stt.profile(self.path)
        self.args.root = str(Path(self.tmp.name)/'second-root')
        self.args.project = 'verify-yet-b'
        self.args.url = 'https://lrs-b.invalid'
        self.args.port = 28184
        b = stt.profile(stt.initialize(self.args))
        ma, mb = stt.check(a), stt.check(b)
        self.assertNotEqual(ma['networks'],mb['networks'])
        self.assertNotEqual(ma['services']['postgres']['volumes'],mb['services']['postgres']['volumes'])
        self.assertNotEqual(ma['services']['lrsql']['ports'],mb['services']['lrsql']['ports'])
        self.assertNotEqual(a['POSTGRES_PASSWORD'],b['POSTGRES_PASSWORD'])
        self.assertEqual(mb['services']['lrsql']['environment']['LRSQL_ALLOWED_ORIGINS'],b['LRSQL_PUBLIC_URL'])
        self.assertEqual(mb['services']['lrsql']['environment']['LRSQL_AUTHORITY_URL'],b['LRSQL_PUBLIC_URL'])

    def test_legacy_named_resources_preserved(self):
        c = stt.profile(self.path)
        c.pop('POSTGRES_DATA_PATH')
        c['COMPOSE_PROJECT_NAME'] = 'yet-lrsql'
        # Remove the bind from the interpolation source as well.
        self.path.write_text('\n'.join(line for line in self.path.read_text().splitlines()
                                     if not line.startswith('POSTGRES_DATA_PATH='))+'\n')
        model = stt.check(c)
        self.assertEqual(model['volumes']['postgres_data']['name'],'yet-lrsql-postgres-data')
        self.assertEqual(model['networks']['yet-internal']['name'],'yet-lrsql-internal')

    def test_refuses_reinitialization(self):
        original = self.path.read_bytes()
        with self.assertRaises(ValueError): stt.initialize(self.args)
        self.assertEqual(original,self.path.read_bytes())

    def test_missing_required_option(self):
        self.path.write_text(self.path.read_text().replace('LRSQL_HTTP_PORT=28183\n',''))
        with self.assertRaisesRegex(ValueError,'Missing'): stt.profile(self.path)

    def test_example_rejected(self):
        self.path.write_text(self.path.read_text().replace('lrs-a.invalid','example.com'))
        with self.assertRaisesRegex(ValueError,'Example'): stt.profile(self.path)

    def test_duplicate_and_expansion_rejected(self):
        for extra in ('POSTGRES_DB=other\n','OTHER=$(touch /tmp/unwanted)\n'):
            original = self.path.read_text()
            self.path.write_text(original+extra)
            with self.assertRaises(ValueError): stt.profile(self.path)
            self.path.write_text(original)

    def test_ambient_override_rejected(self):
        with patch.dict(os.environ, {'LRSQL_HTTP_PORT':'8888'}):
            with self.assertRaisesRegex(ValueError,'exported'): stt.profile(self.path)

    @unittest.skipIf(os.name == 'nt','Unix permissions exercised on Linux')
    def test_private_permissions(self):
        p = Path(stt.profile(self.path)['_files'][1])
        p.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'permissions'): stt.profile(self.path)

    def test_port_collision_before_initialization(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            self.args.port = sock.getsockname()[1]
            self.args.root = str(Path(self.tmp.name)/'collision')
            with self.assertRaises(OSError): stt.initialize(self.args)
            self.assertFalse(Path(self.args.root).exists())

    def test_corrupt_backup_rejected(self):
        p = Path(self.tmp.name)/'backup'
        p.mkdir()
        (p/'SHA256SUMS').write_text('0'*64+'  database.dump\n')
        (p/'database.dump').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'checksum'): stt.validate_backup(p)


if __name__ == '__main__': unittest.main()
