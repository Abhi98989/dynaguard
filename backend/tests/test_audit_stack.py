import tempfile
import unittest
from pathlib import Path
from dynaguard.audit.stack import detect_stacks


class TestAuditStackDetection(unittest.TestCase):
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(detect_stacks(td), set())

    def test_laravel_detection(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'artisan').write_text('php artisan')
            (Path(td) / 'composer.json').write_text('{"require": {"laravel/framework": "^10.0"}}')
            stacks = detect_stacks(td)
            self.assertIn('laravel', stacks)

    def test_flutter_and_nextjs_monorepo(self):
        with tempfile.TemporaryDirectory() as td:
            flutter_dir = Path(td) / 'mobile'
            flutter_dir.mkdir()
            (flutter_dir / 'pubspec.yaml').write_text('name: school_app\n')

            web_dir = Path(td) / 'frontend'
            web_dir.mkdir()
            (web_dir / 'package.json').write_text('{"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}')

            backend_dir = Path(td) / 'server'
            backend_dir.mkdir()
            (backend_dir / 'requirements.txt').write_text('fastapi==0.100.0\n')

            stacks = detect_stacks(td)
            self.assertIn('flutter', stacks)
            self.assertIn('nextjs', stacks)
            self.assertIn('react', stacks)
            self.assertIn('python', stacks)


if __name__ == '__main__':
    unittest.main()
