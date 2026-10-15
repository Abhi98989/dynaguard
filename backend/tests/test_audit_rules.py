import unittest
from dynaguard.audit.rules.laravel import LARAVEL_RULES
from dynaguard.audit.rules.node import NODE_RULES
from dynaguard.audit.rules.nextjs import NEXTJS_RULES
from dynaguard.audit.rules.python import PYTHON_RULES
from dynaguard.audit.rules.flutter import FLUTTER_RULES
from dynaguard.audit.rules.database import DATABASE_RULES


class TestAuditRules(unittest.TestCase):
    def test_laravel_mass_assignment(self):
        rule = next(r for r in LARAVEL_RULES if r.id == 'laravel.mass-assignment')
        vuln = 'class User extends Model { protected $guarded = []; }'
        findings = rule.scan(vuln, 'app/Models/User.php')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, 'high')

        safe = 'class User extends Model { protected $fillable = ["name", "email"]; }'
        self.assertEqual(len(rule.scan(safe, 'app/Models/User.php')), 0)

    def test_node_jwt_decode(self):
        rule = next(r for r in NODE_RULES if r.id == 'node.jwt-decode-without-verify')
        vuln = 'const user = jwt.decode(token);'
        findings = rule.scan(vuln, 'routes/auth.js')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, 'critical')

        safe = 'const user = jwt.verify(token, secret, { algorithms: ["HS256"] });'
        self.assertEqual(len(rule.scan(safe, 'routes/auth.js')), 0)

    def test_nextjs_public_secret_leak(self):
        rule = next(r for r in NEXTJS_RULES if r.id == 'nextjs.public-secret-leak')
        vuln = 'NEXT_PUBLIC_DATABASE_PASSWORD=supersecret'
        findings = rule.scan(vuln, '.env.local')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, 'critical')

        safe = 'DATABASE_PASSWORD=supersecret'
        self.assertEqual(len(rule.scan(safe, '.env.local')), 0)

    def test_python_raw_sql_formatting(self):
        rule = next(r for r in PYTHON_RULES if r.id == 'python.raw-sql-formatting')
        vuln = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")'
        findings = rule.scan(vuln, 'views.py')
        self.assertEqual(len(findings), 1)

        safe = 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))'
        self.assertEqual(len(rule.scan(safe, 'views.py')), 0)

    def test_flutter_disabled_ssl_pinning(self):
        rule = next(r for r in FLUTTER_RULES if r.id == 'flutter.disabled-ssl-pinning')
        vuln = 'client.badCertificateCallback = (cert, host, port) => true;'
        findings = rule.scan(vuln, 'lib/api.dart')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, 'critical')

    def test_database_unbound_port(self):
        rule = next(r for r in DATABASE_RULES if r.id == 'database.unbound-port-publish')
        vuln = 'ports:\n  - "5432:5432"'
        findings = rule.scan(vuln, 'docker-compose.yml')
        self.assertEqual(len(findings), 1)

        safe = 'ports:\n  - "127.0.0.1:5432:5432"'
        self.assertEqual(len(rule.scan(safe, 'docker-compose.yml')), 0)


if __name__ == '__main__':
    unittest.main()
