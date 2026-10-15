"""Audit rules tailored for Flutter and Dart mobile applications."""
import re
from .base import RegexRule

FLUTTER_RULES = [
    RegexRule(
        rule_id='flutter.cleartext-http-base-url',
        layer='config',
        title='Hardcoded unencrypted HTTP base URL in mobile app',
        severity='high',
        confidence='medium',
        pattern=re.compile(r'["\']http://[a-zA-Z0-9.-]+(?::\d+)?(?:/api|/v[0-9]|/graphql)'),
        file_patterns=['.dart'],
        recommendation='Use HTTPS endpoints for all mobile API communication to prevent network eavesdropping and tampering.',
        cwe='CWE-319',
        owasp='M04:2024-Insecure Communication',
        stacks={'flutter'}
    ),
    RegexRule(
        rule_id='flutter.disabled-ssl-pinning',
        layer='config',
        title='Custom badCertificateCallback accepting all SSL certificates',
        severity='critical',
        confidence='high',
        pattern=re.compile(r'badCertificateCallback\s*=\s*\([^)]*\)\s*=>\s*true'),
        file_patterns=['.dart'],
        recommendation='Do not disable SSL verification in production; badCertificateCallback returning true allows Man-in-the-Middle attacks.',
        cwe='CWE-295',
        owasp='M04:2024-Insecure Communication',
        stacks={'flutter'}
    ),
    RegexRule(
        rule_id='flutter.token-in-shared-preferences',
        layer='secret',
        title='Sensitive token stored in plaintext SharedPreferences',
        severity='medium',
        confidence='medium',
        pattern=re.compile(r'SharedPreferences[a-zA-Z0-9_.]*setString\s*\(\s*["\'](?:token|auth|jwt|password|secret|access_token)["\']'),
        file_patterns=['.dart'],
        recommendation='Store authentication tokens and keys in flutter_secure_storage (Keychain / Keystore) instead of SharedPreferences.',
        cwe='CWE-312',
        owasp='M02:2024-Insecure Data Storage',
        stacks={'flutter'}
    ),
    RegexRule(
        rule_id='flutter.android-cleartext-traffic',
        layer='config',
        title='Android manifest allows cleartext HTTP traffic',
        severity='high',
        confidence='high',
        pattern=re.compile(r'android:usesCleartextTraffic\s*=\s*["\']true["\']'),
        file_patterns=['AndroidManifest.xml'],
        recommendation='Set android:usesCleartextTraffic="false" to enforce HTTPS throughout the application.',
        cwe='CWE-319',
        owasp='M04:2024-Insecure Communication',
        stacks={'flutter'}
    ),
    RegexRule(
        rule_id='flutter.android-debuggable',
        layer='config',
        title='Android manifest specifies debuggable application',
        severity='medium',
        confidence='high',
        pattern=re.compile(r'android:debuggable\s*=\s*["\']true["\']'),
        file_patterns=['AndroidManifest.xml'],
        recommendation='Ensure android:debuggable="false" for all release builds to prevent debugging attachment and memory dumping.',
        cwe='CWE-489',
        owasp='M01:2024-Improper Platform Usage',
        stacks={'flutter'}
    )
]
